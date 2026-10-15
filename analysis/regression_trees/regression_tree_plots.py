"""Combine saved regression-tree SVGs by norm, without fitting trees again."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


OVERVIEW_FILENAME = "regressiontrees_alle_normen.svg"
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
TARGET_UNITS = {
    "x_mean": "Zeitmittel des Mitigationsanteils · %",
    "final_temperature": "Endtemperatur · °C",
    "cumulative_emissions": "Kumulierte Emissionen · GtC",
    "first_time_x95": "Erste Erreichung von x ≥ 95 % · Jahre; 0 = nie",
    "bool_x95": "Anteil der Läufe mit x ≥ 95 % irgendwann · %",
    "oscillation_occurrence": "Anteil der Läufe mit mindestens 2 vollständigen Zyklen · %",
    "oscillations_per_500_years": "Gespeicherte Zykluszahl · pro 500 Jahre",
    "final_x": "Mitigationsanteil am Simulationsende · %",
    "median_period": "Mediane Periodendauer · Jahre",
    "oscillation_amplitude": "Gespeicherte Oszillationsamplitude · Prozentpunkte",
    "damping_index": "Dämpfungsindex · dimensionslos",
    "damping_rate": "Dämpfungsrate · 1/Jahr",
}


def _element(parent, tag, **attributes):
    return ET.SubElement(parent, f"{{{SVG_NS}}}{tag}",
                         {key.replace("_", "-"): str(value) for key, value in attributes.items()})


def _label(parent, x, y, content, size=18, bold=False, color="#183344", anchor="start"):
    element = _element(parent, "text", x=f"{x:g}", y=f"{y:g}",
                       font_family="DejaVu Sans, sans-serif", font_size=size,
                       font_weight="700" if bold else "400", fill=color, text_anchor=anchor)
    element.text = content
    return element


def _tree_panel(path: Path, prefix: str):
    """Preserve native vectors and font sizes; remove repeated plot headings."""
    source = ET.parse(path).getroot()
    x, y, width, height = map(float, source.attrib["viewBox"].split())
    axes = next((node for node in source.iter() if node.get("id") == "axes_1"), None)
    panel = ET.Element(f"{{{SVG_NS}}}g")
    if axes is None:
        # Accept complete SVGs from other renderers without cropping their content.
        panel.extend(list(source))
        top, panel_height = y, height
    else:
        panel.extend(node for node in source if node.tag == f"{{{SVG_NS}}}defs")
        panel.append(axes)
        # render_tree places the axes between 13% and 87% of the figure height.
        # Keep extra space for node boxes protruding beyond the axes.
        top, panel_height = y + 0.10 * height, 0.84 * height
    panel.set("transform", f"translate({-x:g} {-top:g})")
    identifiers = {node.attrib["id"]: prefix + node.attrib["id"]
                   for node in panel.iter() if "id" in node.attrib}

    def references(value):
        return re.sub(r"url\(#([^)]*)\)",
                      lambda match: f"url(#{identifiers.get(match[1], match[1])})", value)

    for node in panel.iter():
        for key, value in list(node.attrib.items()):
            if key == "id":
                node.set(key, identifiers[value])
            elif key in ("href", f"{{{XLINK_NS}}}href") and value.startswith("#"):
                node.set(key, "#" + identifiers.get(value[1:], value[1:]))
            else:
                node.set(key, references(value))
        if node.tag == f"{{{SVG_NS}}}style" and node.text:
            node.text = references(node.text)
    return panel, width, panel_height


def _mae(target, value):
    if target in {"final_x", "x_mean", "oscillation_amplitude", "bool_x95", "oscillation_occurrence"}:
        return f"{100 * value:.2f} Prozentpunkte".replace(".", ",")
    unit = {"median_period": " Jahre", "first_time_x95": " Jahre", "damping_index": "",
            "damping_rate": " / Jahr", "final_temperature": " °C", "cumulative_emissions": " GtC",
            "oscillations_per_500_years": " / 500 Jahre"}[target]
    return f"{value:.3g}{unit}".replace(".", ",")


def _counts(report):
    if "eligible_rows" not in report:
        return "Anzahl gültiger Läufe nicht im Bericht angegeben"
    return (f"Gültig: {report['eligible_rows']} / {report['total_rows']} Läufe"
            f" · Training: {report.get('train_rows', 0)} · Test: {report.get('test_rows', 0)}")


def create_regression_tree_overview(result_dir: Path, output_path: Path | None = None) -> Path:
    """One norm per section, one target per column; all graphics are embedded."""
    result_dir = Path(result_dir)
    manifest_path = result_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    mode = manifest.get("analysis_mode", "per_norm")
    title = {"pooled_common": "Regression Trees über alle Normen · gemeinsame Parameter",
             "per_norm_common": "Regression Trees je Norm · gemeinsame Parameter"}.get(
                 mode, "Regression Trees – alle Normen")
    if manifest.get("analysis_variant_label"):
        title += " · " + manifest["analysis_variant_label"]
    reports = json.loads((result_dir / "reports.json").read_text(encoding="utf-8"))
    if not reports:
        raise ValueError("No regression-tree reports found")
    folders = {}
    for path in sorted(result_dir.glob("*/*/report.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        key = (report["scenario"], report["target"])
        if key in folders:
            raise ValueError(f"Duplicate regression-tree report: {key}")
        folders[key] = path.parent
    scenarios = list(dict.fromkeys(report["scenario"] for report in reports))
    targets = list(dict.fromkeys(report["target"] for report in reports))
    lookup = {(report["scenario"], report["target"]): report for report in reports}
    if len(lookup) != len(reports):
        raise ValueError("Duplicate scenario/target in reports.json")
    panels = {}
    for index, report in enumerate(reports):
        key = (report["scenario"], report["target"])
        if report["status"] == "fitted":
            panels[key] = _tree_panel(folders[key] / "tree.svg", f"tree{index}_")

    margin, gap, padding = 36, 24, 24
    heading_height, card_header, card_footer, section_gap = 58, 76, 108, 32
    column_widths = [max([864, *(panel[1] for (norm, name), panel in panels.items()
                                if name == target)]) + 2 * padding for target in targets]
    row_heights = {norm: max([240, *(panel[2] for (name, target), panel in panels.items()
                                     if name == norm)]) for norm in scenarios}
    width = 2 * margin + sum(column_widths) + gap * (len(targets) - 1)
    height = 150 + sum(heading_height + card_header + row_heights[norm] + card_footer
                       + section_gap for norm in scenarios) + 60
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    sheet = ET.Element(f"{{{SVG_NS}}}svg", {
        "version": "1.1", "viewBox": f"0 0 {width:g} {height:g}",
        "width": "1800", "height": f"{1800 * height / width:g}",
        "role": "img", "aria-labelledby": "overview_title overview_description",
    })
    _element(sheet, "title", id="overview_title").text = title
    _element(sheet, "desc", id="overview_description").text = (
        "Ein Abschnitt pro Norm, eine Spalte pro Zielvariable. Vollständige gespeicherte "
        "Trees als eingebettete Vektoren. Fehlende Trees werden mit ihrem Status gezeigt. "
        "Zielvariablen und Parameternamen bleiben unverändert."
    )
    _element(sheet, "rect", width=f"{width:g}", height=f"{height:g}", fill="#eaf0f5")
    fitted = len(panels)
    _label(sheet, margin, 46, title, 32, True)
    norm_count = len(manifest["sources"]) if mode == "pooled_common" else len(scenarios)
    _label(sheet, margin, 80,
           f"{norm_count} Normen · {len(targets)} Zielvariablen · {fitted} Trees"
           " · zum Lesen der Knoten in die Vektorgrafik hineinzoomen", 20)
    _label(sheet, margin, 112,
           "Ja / Nein: der Bedingung folgen · Blatt: Mittelwert und Standardabweichung der Trainingsläufe"
           " · Perioden-, Amplituden- und Dämpfungsziele: nur gültige schwingende Verläufe", 18, color="#526579")
    if mode in {"pooled_common", "per_norm_common"}:
        _label(sheet, margin, 138, "Entscheidungsparameter: " + ", ".join(manifest["common_feature_names"]),
               17, color="#526579")
    top = 150
    for norm_index, norm in enumerate(scenarios):
        section = _element(sheet, "g", id=f"norm_section_{norm_index}")
        section.set("data-scenario", norm)
        _label(section, margin, top + 34, f"{norm_index + 1}. {norm}", 27, True)
        left = margin
        card_top = top + heading_height
        card_height = card_header + row_heights[norm] + card_footer
        for target, column_width in zip(targets, column_widths):
            report = lookup.get((norm, target), {"status": "not_analyzed"})
            card = _element(section, "g")
            card.set("data-target", target)
            card.set("data-status", report["status"])
            if report.get("reason"):
                _element(card, "desc").text = report["reason"]
            _element(card, "rect", x=f"{left:g}", y=f"{card_top:g}",
                     width=f"{column_width:g}", height=f"{card_height:g}", rx=14,
                     fill="#ffffff", stroke="#cad6df", stroke_width=1.2)
            _label(card, left + padding, card_top + 30, target, 23, True)
            _label(card, left + padding, card_top + 55, TARGET_UNITS[target], 17, color="#526579")
            if report["status"] == "fitted":
                panel, panel_width, _ = panels[(norm, target)]
                placed = _element(card, "g", transform=(
                    f"translate({left + (column_width - panel_width) / 2:g} {card_top + card_header:g})"))
                placed.set("data-tree-panel", f"{norm_index}:{target}")
                placed.append(panel)
            else:
                status = {"insufficient_data": "Kein Tree: zu wenig gültige Daten",
                          "constant_training_target": "Kein Tree: Zielwert im Training konstant",
                          "unavailable": "Kein Tree: Zielvariable nicht verfügbar",
                          "not_analyzed": "Nicht ausgewertet"}.get(report["status"], report["status"])
                center = left + column_width / 2
                middle = card_top + card_header + row_heights[norm] / 2
                _label(card, center, middle - 12, status, 22, True, color="#647689", anchor="middle")
                _label(card, center, middle + 24, _counts(report), 17, color="#647689", anchor="middle")
                if "train_blocks" in report:
                    _label(card, center, middle + 52,
                           f"Trainingsblöcke: {report['train_blocks']} · Testblöcke: {report['test_blocks']}",
                           17, color="#647689", anchor="middle")
            footer = card_top + card_header + row_heights[norm]
            if report["status"] == "fitted":
                _label(card, left + padding, footer + 22, _counts(report), 16, color="#526579")
                _label(card, left + padding, footer + 46,
                       f"Test-MAE: {_mae(target, report['test_metrics']['mae'])}"
                       f" · Vergleich (Trainingsmittelwert): {_mae(target, report['baseline_test_metrics']['mae'])}",
                       16, color="#526579")
                notes = []
                if report.get("train_blocks", 0) < 30 or report.get("test_blocks", 0) < 10:
                    notes.append("Kleine Stichprobe; Ergebnis explorativ")
                if not report.get("beats_mean_baseline", True):
                    notes.append("Test-MAE nicht besser als Mittelwert-Vergleich")
                if notes:
                    _label(card, left + padding, footer + 74, " · ".join(notes), 16, color="#96601b")
                if report.get("saved_definition_note"):
                    _label(card, left + padding, footer + 96, report["saved_definition_note"],
                           15, color="#96601b")
            left += column_width + gap
        top = card_top + card_height + section_gap
    _label(sheet, margin, top + 24,
           "Darstellung aus gespeicherten Tree-SVGs und Berichten; keine erneuten Fits oder Simulationen.",
           18, color="#526579")
    output_path = Path(output_path) if output_path is not None else result_dir / OVERVIEW_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(sheet).write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path, help="Saved regression-tree result folder")
    parser.add_argument("--output-path", type=Path, help="Default: regressiontrees_alle_normen.svg in the result folder")
    args = parser.parse_args()
    print(f"Saved regression-tree overview: {create_regression_tree_overview(args.input_root, args.output_path)}")


if __name__ == "__main__":
    main()
