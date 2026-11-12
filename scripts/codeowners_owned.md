# codeowners_owned.py

Says whether `.github/CODEOWNERS` owns a path, so a change to that file can be
checked against a fixed table of paths instead of read by eye.

## Why it exists

`.github/CODEOWNERS` has no catch-all line. A path is owned only because a line
names it, and a path no line names is released: a change to it needs no
code-owner review. A line removed by mistake, or a release line added after the
shared set at the bottom, silently takes a control away. The table in
`SAMPLES` has one path for each class the file keeps and one for each class it
releases, and the check fails when the file and the table disagree.

## Reading rules

GitHub applies the last pattern that matches a path. A pattern with no slash
matches at any depth, a leading or middle slash anchors it to the root, a
trailing slash means a directory and everything under it, `*` stays inside one
directory and `**` crosses them. A matching line that names no owner releases
the path. Negation and character classes are not supported and are refused.

## Use

    python3 scripts/codeowners_owned.py --codeowners .github/CODEOWNERS --check
    git ls-files > tree.txt
    python3 scripts/codeowners_owned.py --codeowners .github/CODEOWNERS --count --tree tree.txt

`--check` prints one line per mismatch and ends `GREEN` (exit 0) or `RED`
(exit 1). It also fails on a bare catch-all line. `--count` prints
`owned N of M` for the listed paths.

## What changing a class takes

Edit `.github/CODEOWNERS` and the `SAMPLES` table together. The shared lines at
the bottom of the file are the standards escape hatches: the standards workflow
checks them, and they stay last.

## Tests

`test_codeowners_owned.py` checks the live file against the table, checks that
the old file (kept in `testdata/codeowners/before.txt`) disagrees with the table
on exactly the released classes, checks that removing the line for scripts or
for `package.json` turns the check red, and covers the matcher. It reads files
and runs nothing else, so it runs in the job that holds no secret.
