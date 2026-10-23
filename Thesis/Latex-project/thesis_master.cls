% Adapted from thesis_CG_template_v173/thesis_CG.cls in Bachelorarbeit.zip.
% Preserve its page geometry, title layout, chapter layout and running headings.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{thesis_master}[2026/10/23 Master's thesis layout based on thesis_CG]
\LoadClass[11pt,a4paper,twoside,openright]{report}

\newif\ifthesis@german
\DeclareOption{english}{\thesis@germanfalse}
\DeclareOption{german}{\thesis@germantrue}
\DeclareOption{draft}{\PassOptionsToPackage{draft}{graphicx}}
\ExecuteOptions{english}
\ProcessOptions\relax

\RequirePackage[T1]{fontenc}
\ifthesis@german
  \RequirePackage[ngerman]{babel}
\else
  \RequirePackage[english]{babel}
\fi
\RequirePackage{graphicx}
\RequirePackage{amsmath}
\RequirePackage{amssymb}
\RequirePackage{fancyhdr}
\RequirePackage{url}
\RequirePackage{cite}
\RequirePackage{typearea}
\RequirePackage[labelfont=bf,font=small]{caption}
% The German bachelor project used paragraph spacing rather than indentation.
\RequirePackage{parskip}

% Original type area: 16 x 21 cm, 0.75 cm binding correction, shifted down 1 cm.
\areaset[0.75cm]{16cm}{21cm}
\addtolength{\topmargin}{1cm}
\setlength{\headheight}{14pt}
\addtolength{\topmargin}{-2pt}
\renewcommand{\floatpagefraction}{.9}
\renewcommand{\textfraction}{.15}
\renewcommand{\arraystretch}{1.2}
\bibliographystyle{abbrv}

% Keep inserted verso pages completely blank in the two-sided layout.
\def\cleardoublepage{\clearpage\if@twoside\ifodd\c@page\else
  \hbox{}\thispagestyle{empty}\newpage
  \if@twocolumn\hbox{}\newpage\fi\fi\fi}

\newcommand{\type}[1]{\gdef\@type{#1}}
\newcommand{\dept}[1]{\gdef\@dept{#1}}
\newcommand{\submitdate}[1]{\gdef\@submitdate{#1}}
\newcommand{\firstSupervisor}[1]{\gdef\@firstSupervisor{#1}}
\newcommand{\secondSupervisor}[1]{\gdef\@secondSupervisor{#1}}
\newcommand{\shorttitle}[1]{\gdef\@shorttitle{#1}}

\fancyhf{}
\setlength{\headwidth}{\textwidth}
\fancyhead[LE,RO]{\thepage}
\fancyhead[LO]{\rightmark}
\fancyhead[RE]{\leftmark}
\fancyfoot[C]{\textsc{\@shorttitle}}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0.4pt}

\newcommand{\generatetitle}{%
  \pagenumbering{roman}
  \pagestyle{plain}
  \thispagestyle{empty}
  \begin{center}
    \vspace*{4mm}
    \includegraphics[height=1.5cm]{unilogo.jpg}\par
    \vspace{4mm}
    {\LARGE\textsc{\@dept}\par}
    \vfill
    {\LARGE\emph{\@type}\par}
    \vspace{8mm}
    {\huge\bfseries\@title\par}
    \vspace{8mm}
    {\LARGE\@author\par}
    \vspace{32mm}
    {\large\@submitdate\par}
    \vfill
    \begin{tabular}{ll}
      \large\ifthesis@german Erstgutachter:\else First supervisor:\fi
        & \large\@firstSupervisor\\
      \large\ifthesis@german Zweitgutachter:\else Second supervisor:\fi
        & \large\@secondSupervisor
    \end{tabular}
  \end{center}
}

\newenvironment{prefacesection}[1]
  {\thispagestyle{empty}\centerline{\Large\textbf{#1}}\medskip}
  {}

\newcommand{\startTextChapters}{%
  \cleardoublepage
  \pagestyle{fancy}
  \pagenumbering{arabic}
}
