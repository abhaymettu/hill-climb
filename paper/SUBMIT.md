# Submitting the paper to arXiv

Nothing has been submitted. These are the steps for Abhay to do from his own arXiv account.

## 1. Build the upload

```sh
cd paper
./make-arxiv.sh        # writes paper/arxiv.tar.gz and lists its contents
```

The tarball is flat: `main.tex`, the eight section files, the three table files, `refs.bib`, `main.bbl` and the two
figures (`bench-results-light.png`, `bench-results-opus-light.png`). The script rewrites the figure paths from
`../assets/` to the same folder and generates `main.bbl`, because arXiv does not run BibTeX. `hill-climb.pdf` in
this folder is the same paper, built with `tectonic main.tex`; use it to check what arXiv renders.

## 2. Endorsement (first submission to cs.SE)

arXiv asks a first-time submitter to a category for an endorsement. Start the submission; if arXiv says the account
needs one, it shows a six-character endorsement code. Send that code to someone who has posted to cs.SE (or cs.AI)
and ask them to endorse at https://arxiv.org/auth/endorse. An account registered with a university email address is
sometimes endorsed automatically.

## 3. Submit

1. https://arxiv.org/submit, start a new submission.
2. License: CC BY 4.0 (matches an open-source repo; any arXiv license is fine).
3. Archive and primary category: **Computer Science, Software Engineering (cs.SE)**.
4. Upload `paper/arxiv.tar.gz`. arXiv unpacks it and compiles with pdfLaTeX. Check the processed PDF matches
   `hill-climb.pdf` (10 pages, two figures, four tables).
5. Metadata:
   - Title: `Does a hill-climbing skill make coding agents better optimizers? A controlled benchmark of process instructions, and a check of blind LLM judges against real A/B tests`
   - Authors: `Abhay Mettu`
   - Abstract: paste the text of `abstract.tex` without the `\begin{abstract}`/`\end{abstract}` lines; replace
     `$\kappa$` with `kappa`, `\%` with `%`, `\texttt{claude -p}` with `claude -p`, and the ``` `` ''``` quotes with plain quotes.
   - Comments: `10 pages, 2 figures. Code, tasks and all 156 agent transcripts: https://github.com/abhaymettu/hill-climb`
   - Cross-list (suggested): **cs.AI**. cs.LG is a reasonable second cross-list.
6. Preview, then submit. Announcements go out on the next weekday cycle.

## After it is announced

Add the arXiv link and a BibTeX entry to the README and `site/meta.json`.
