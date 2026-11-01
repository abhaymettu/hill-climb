#!/bin/sh
# Builds paper/arxiv.tar.gz: flat sources, figures beside them, and the .bbl that arXiv needs (it does not run BibTeX).
set -eu
cd "$(dirname "$0")"
out=$(mktemp -d)
cp main.tex abstract.tex intro.tex related.tex method.tex results.tex fix.tex taste.tex limits.tex \
   results_table.tex results-opus_table.tex taste_table.tex refs.bib "$out/"
cp ../assets/bench-results-light.png ../assets/bench-results-opus-light.png "$out/"
sed -i.bak 's#\.\./assets/##' "$out/results.tex" && rm "$out/results.tex.bak"
(cd "$out" && tectonic --keep-intermediates main.tex >/dev/null 2>&1 && rm -f main.pdf main.aux main.log main.out main.blg main.toc)
test -s "$out/main.bbl"
tar -czf arxiv.tar.gz -C "$out" .
rm -rf "$out"
tar -tzf arxiv.tar.gz | sort
