#!/usr/bin/env bash
# Tests for guard-todo-worker-git.sh — run from anywhere.
# The guard limits todo-worker / todo-verifier Bash calls to staging-only git
# (spec §4.1). The cases that matter are the disguises: wrappers, absolute
# paths, compound commands, bash -c, $(...), a second line — and the harmless
# mention of "git commit" inside a grep, which must still be allowed.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/guard-todo-worker-git.sh"
PASS=0; FAIL=0

event() {
  python3 -c 'import json, sys; print(json.dumps({"agent_type": sys.argv[1], "tool_input": {"command": sys.argv[2]}}))' "$1" "$2"
}

assert_deny() {
  local name="$1" out
  out=$(event "$2" "$3" | bash "$HOOK" 2>/dev/null)
  if grep -q '"permissionDecision": "deny"' <<< "$out"; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected deny)"; echo "  got: $out"; FAIL=$((FAIL+1))
  fi
}

assert_allow() {
  local name="$1" out
  out=$(event "$2" "$3" | bash "$HOOK" 2>/dev/null)
  if [ -z "$out" ]; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected allow)"; echo "  got: $out"; FAIL=$((FAIL+1))
  fi
}

assert_deny_msg() {  # name agent command text-the-reason-must-contain
  local name="$1" out
  out=$(event "$2" "$3" | bash "$HOOK" 2>/dev/null)
  if grep -q '"permissionDecision": "deny"' <<< "$out" && grep -qF -- "$4" <<< "$out"; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected deny mentioning '$4')"; echo "  got: $out"; FAIL=$((FAIL+1))
  fi
}

assert_raw() {  # name deny|allow raw-event-json
  local name="$1" out ok=0
  out=$(printf '%s' "$3" | bash "$HOOK" 2>/dev/null)
  if [ "$2" = deny ]; then grep -q '"permissionDecision": "deny"' <<< "$out" && ok=1
  else [ -z "$out" ] && ok=1; fi
  if [ $ok -eq 1 ]; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected $2)"; echo "  got: $out"; FAIL=$((FAIL+1))
  fi
}

W=todo-worker
assert_deny  "worker: git commit"                  $W 'git commit -m x'
assert_deny  "worker: git push"                      $W 'git push origin HEAD'
assert_deny  "worker: absolute git with -C"          $W '/usr/bin/git -C /tmp/wt commit -m x'
assert_deny  "worker: rtk wrapper"                   $W 'rtk git commit -m x'
assert_deny  "worker: env prefix"                    $W 'FOO=1 git push'
assert_deny  "worker: compound after cd"             $W 'cd /tmp/wt && git switch main'
assert_deny  "worker: git stash"                     $W 'git stash push -m x'
assert_deny  "worker: git checkout"                  $W 'git checkout -- a.py'
assert_deny  "worker: git -c option then reset"      $W 'git -c core.x=y reset --hard'
assert_deny  "worker: bash -c"                       $W 'bash -c "git push"'
assert_deny  "worker: command substitution"          $W 'echo $(git reset --hard)'
assert_deny  "worker: second line"                   $W $'git add a.py\ngit commit -m x'
assert_deny  "worker: gh"                            $W 'gh pr create --fill'
assert_deny  "worker: unparseable quoting"           $W 'git add "a.py'
assert_deny  "verifier: git commit"                  todo-verifier 'git commit -m x'
assert_allow "worker: git add -A"                    $W 'git -C /tmp/wt add -A'
assert_allow "worker: status porcelain"              $W '/usr/bin/git -C /tmp/wt status --porcelain'
assert_allow "worker: write-tree"                    $W 'git write-tree'
assert_allow "worker: diff cached vs origin/main"    $W 'git diff --cached --name-status origin/main'
assert_allow "worker: mention inside grep"           $W 'grep -rn "git commit" docs/'
assert_allow "worker: pytest via slot_env"           $W 'python3 scripts/todos/slot_env.py 1 -- python -m pytest apps/x'
assert_allow "main session (no agent_type)"          "" 'git commit -m x'
assert_allow "another agent type"                    code-review-orchestrator 'git push'

# K1 — shell reserved words hide the real command
assert_deny  "K1: if/else hides commit"              $W 'if git diff --cached --quiet; then :; else git commit -m x; fi'
assert_deny  "K1: if/then"                           $W 'if true; then git commit -m x; fi'
assert_deny  "K1: for/do"                            $W 'for f in a; do git checkout -- $f; done'
assert_deny  "K1: while/do"                          $W 'while false; do git push; done'
assert_deny  "K1: brace group"                       $W '{ git push; }'
assert_deny  "K1: negation"                          $W '! git push'
assert_deny  "K1: function body"                     $W 'f(){ git push; }; f'
assert_deny  "K1: coproc"                            $W 'coproc git push'
assert_deny  "K1: builtin command"                   $W 'builtin command git push'
assert_deny  "K1: case arm"                          $W 'case "$x" in a) git push;; esac'
assert_allow "K1: case pattern * is data"            $W 'case "$x" in *) git status;; esac'
assert_allow "K1: later case patterns are data"      $W 'case "$x" in a) git status;; *) git add x;; esac'
assert_allow "K1: test bracket in if"                $W 'if [ -f a.py ]; then git add a.py; fi'

# K2 — other entrances to a shell
assert_deny  "K2: bash -lc"                          $W 'bash -lc "git push"'
assert_deny  "K2: bash -e -c"                        $W 'bash -e -c "git push"'
assert_deny  "K2: bash -c --"                        $W 'bash -c -- "git push"'
assert_deny  "K2: dash -c"                           $W 'dash -c "git push"'
assert_deny  "K2: bash -o pipefail -c"               $W 'bash -o pipefail -c "git push"'
assert_deny  "K2: here-string into bash"             $W 'bash <<< "git push"'
assert_deny  "K2: piped into bash"                   $W 'echo "git push" | bash'
assert_deny  "K2: piped into sh -s"                  $W 'echo "git push" | sh -s'
assert_deny  "K2: process substitution into bash"    $W 'bash <(echo git push)'
assert_allow "K2: sh -c with allowed git"            $W 'sh -c "git status"'
assert_allow "K2: shell running a script file"       $W 'bash .claude/hooks/test-x.sh'

# K3 — the program name is built at runtime
assert_deny  "K3: \$(echo git)"                      $W '$(echo git) push'
assert_deny  "K3: backtick program"                  $W '`echo git` push'
assert_deny  "K3: quoted \$(echo git)"               $W '"$(echo git)" push'
assert_deny  "K3: variable program"                  $W 'G=git; $G push'
assert_deny  "K3: \${G} program"                     $W '${G} push'
assert_deny  "K3: ANSI-C quoted program"             $W $'$\'\\x67it\' push'
assert_deny  "K3: brace expansion"                   $W '{git,push}'
assert_deny  "K3: glob ?"                            $W '/usr/bin/gi? push'
assert_deny  "K3: glob *"                            $W '/usr/bin/g*t push'
assert_allow "K3: specials in arguments are fine"    $W 'git diff -- "*.py" "$F"'

# K4 — redirections before or glued to the program
assert_deny  "K4: redirect before program"           $W '>x git commit -m x'
assert_deny  "K4: stdin redirect before program"     $W '</dev/null git push'
assert_deny  "K4: redirect glued to git"             $W 'git>/dev/null commit -m x'
assert_deny_msg "K4: message names the subcommand"   $W 'git>/dev/null commit -m x' 'git commit is reserved'
assert_deny  "K4: 2>&1 before program"               $W '2>&1 git commit -m x'
assert_allow "K4: 2>&1 into a pipe"                  $W 'python3 -m pytest -q 2>&1 | tail -5'

# K5 — wrappers
assert_deny  "K5: timeout"                           $W 'timeout 60 git commit -m x'
assert_deny  "K5: nice"                              $W 'nice git push'
assert_deny  "K5: nice -n 5"                         $W 'nice -n 5 git push'
assert_deny  "K5: stdbuf -oL"                        $W 'stdbuf -oL git push'
assert_deny  "K5: caffeinate"                        $W 'caffeinate git push'
assert_deny  "K5: env -u"                            $W 'env -u FOO git push'
assert_deny  "K5: sudo -u"                           $W 'sudo -u root git push'
assert_deny  "K5: env -S"                            $W 'env -S "git push"'
assert_deny  "K5: find -exec"                        $W 'find . -maxdepth 0 -exec git commit -m x \;'
assert_deny  "K5: xargs git (bare)"                  $W 'echo commit | xargs git'
assert_deny  "K5: xargs -n 1 git (bare)"             $W 'xargs -n 1 git'
assert_allow "K5: bare git alone"                    $W 'git'
assert_allow "K5: git --version"                     $W 'git --version'
assert_allow "K5: timeout with allowed git"          $W 'timeout 60 git status'
assert_allow "K5: command -v git"                    $W 'command -v git'

# K6 — dashed git-core binaries
assert_deny  "K6: git-core/git-commit"               $W '/usr/libexec/git-core/git-commit -m x'
assert_allow "K6: git-status"                        $W 'git-status'

# K7 — only a few git global options
assert_deny  "K7: -c"                                $W 'git -c core.pager=x status'
assert_deny  "K7: --exec-path"                       $W 'git --exec-path=/tmp status'
assert_deny  "K7: --config-env"                      $W 'git --config-env=core.pager=X status'
assert_deny  "K7: --attr-source"                     $W 'git --attr-source=HEAD status'
assert_allow "K7: allowed globals"                   $W 'git -C /tmp/wt --git-dir .git --work-tree=. --no-pager -P --no-optional-locks status'
assert_allow "K7: --git-dir= form"                   $W 'git --git-dir=.git --work-tree . log --oneline -1'

# K8 — allowed subcommands that move refs or run commands
assert_deny  "K8: fetch --upload-pack="              $W 'git fetch --upload-pack=/tmp/x origin'
assert_deny  "K8: fetch --upload-pack VALUE"         $W 'git fetch --upload-pack /tmp/x origin'
assert_deny  "K8: fetch refspec with :"              $W 'git fetch origin main:main'
assert_deny  "K8: fetch forced glob refspec"         $W 'git fetch origin +refs/heads/*:refs/heads/*'
assert_deny  "K8: diff --output"                     $W 'git diff --output=/tmp/x'
assert_deny  "K8: diff --outp abbreviation"          $W 'git diff --outp=/tmp/x'
assert_deny  "K8: log --ext-diff"                    $W 'git log --ext-diff -p'
assert_deny  "K8: show --textconv"                   $W 'git show --textconv HEAD'
assert_allow "K8: fetch origin main"                 $W 'git fetch origin main'
assert_allow "K8: fetch origin"                      $W 'git fetch origin'
assert_allow "K8: diff --cached --stat"              $W 'git diff --cached --stat'
assert_allow "K8: diff --text --no-ext-diff"         $W 'git diff --text --no-ext-diff --no-textconv'
assert_allow "K8: log --oneline -3"                  $W 'git log --oneline -3'
assert_allow "K8: show HEAD:path"                    $W 'git show HEAD:path'
assert_allow "K8: rev-parse HEAD"                    $W 'git rev-parse HEAD'
assert_allow "K8: write-tree"                        $W 'git write-tree'
assert_allow "K8: add -A"                            $W 'git add -A'
assert_allow "K8: mv a b"                            $W 'git mv a b'
assert_allow "K8: rm --cached x"                     $W 'git rm --cached x'
assert_allow "K8: status porcelain untracked=no"     $W 'git status --porcelain --untracked-files=no'

# K9 — heredoc bodies are data
assert_allow "K9: quoted heredoc with apostrophe"    $W $'cat > n.txt <<\'EOF\'\ndon\'t forget\nEOF'
assert_allow "K9: heredoc mentioning git commit"     $W $'cat > notes.md <<\'EOF\'\nthen run\ngit commit -m x\nEOF'
assert_deny  "K9: heredoc into bash"                 $W $'bash <<\'EOF\'\ngit push\nEOF'
assert_deny  "K9: unquoted heredoc runs \$(...)"     $W $'cat <<EOF\n$(git push)\nEOF'
assert_deny  "K9: unterminated heredoc"              $W $'cat <<EOF\ngit push'
assert_deny  "K9: command after the heredoc"         $W $'cat > n.txt <<EOF\nx\nEOF\ngit push'
assert_allow "K9: here-string into cat is data"      $W 'cat <<< "git push"'

# K10 — unexpected hook input
assert_raw   "K10: tool_input is a string"           deny  '{"agent_type": "todo-worker", "tool_input": "git push"}'
assert_raw   "K10: command is a list"                deny  '{"agent_type": "todo-worker", "tool_input": {"command": ["git", "push"]}}'
assert_raw   "K10: no tool_input"                    deny  '{"agent_type": "todo-verifier"}'
assert_raw   "K10: other agent, string tool_input"   allow '{"agent_type": "code-review-orchestrator", "tool_input": "git push"}'
assert_raw   "K10: main session, list command"       allow '{"tool_input": {"command": ["git", "push"]}}'

# R2.1 — source / . fed by stdin or a process substitution
assert_deny  "R2.1: source <(...)"                   $W 'source <(echo git push)'
assert_deny  "R2.1: . <(...)"                        $W '. <(echo git push)'
assert_deny  "R2.1: source /dev/stdin <<<"           $W 'source /dev/stdin <<< "git push"'
assert_deny  "R2.1: piped into source /dev/stdin"    $W 'echo "git push" | source /dev/stdin'
assert_deny  "R2.1: source with no operand"          $W 'source'
assert_allow "R2.1: source a plain file"             $W 'source .venv/bin/activate'
assert_allow "R2.1: . a plain file"                  $W '. .venv/bin/activate && git status'

# R2.2 — zsh precommand modifiers and reserved words
assert_deny  "R2.2: noglob"                          $W 'noglob git commit -m x'
assert_deny  "R2.2: nocorrect"                       $W 'nocorrect git push'
assert_deny  "R2.2: repeat N"                        $W 'repeat 1 git push'
assert_deny  "R2.2: repeat N { }"                    $W 'repeat 1 { git push }'
assert_deny  "R2.2: =git path lookup"                $W '=git push'
assert_deny  "R2.2: { } always { }"                  $W '{ true } always { git push }'
assert_allow "R2.2: noglob with allowed git"         $W 'noglob git add *.py'

# R2.3 — fetch --stdin reads refspecs from a pipe
assert_deny  "R2.3: fetch --stdin"                   $W 'echo main:main | git fetch --stdin origin'

# R2.4 — reserved words count only when unquoted
assert_deny  "R2.4: quoted 'case' is not a case"     $W "'case'; git push; (true)"

# R2.5 — \r is part of a word, not whitespace
assert_deny  "R2.5: <<EOF\\r terminator"             $W $'cat <<EOF\r\nx\nEOF\r\ngit push\nEOF\n'

# R2.6 — <<- heredoc, a shell script fed by stdin, find -execdir / -ok
assert_allow "R2.6: <<- tab-stripped terminator"     $W $'cat <<-EOF\n\tgit commit -m x\n\tEOF'
assert_deny  "R2.6: command after a <<- heredoc"     $W $'cat <<-EOF\nx\n\tEOF\ngit push'
assert_deny  "R2.6: pipe into bash script.sh"        $W 'printf y | bash install.sh'
assert_deny  "R2.6: stdin redirect into bash script" $W 'bash install.sh < answers.txt'
assert_deny  "R2.6: find -execdir"                   $W 'find . -execdir git push \;'
assert_deny  "R2.6: find -ok"                        $W 'find . -ok git commit -m x \;'
assert_allow "R2.6: find -exec allowed git +"        $W 'find . -name "*.py" -exec git add {} +'

# Everyone else is never denied, however odd the command
assert_allow "main session: runtime program name"    "" '$(echo git) push'
assert_allow "main session: shell reading stdin"     "" 'bash <<< "git push"'
assert_allow "other agent: unparseable quoting"      code-review-orchestrator 'git add "a.py'

OUT=$(echo 'not json' | bash "$HOOK" 2>/dev/null)
if [ -z "$OUT" ]; then echo "PASS: malformed JSON fails open"; PASS=$((PASS+1)); else echo "FAIL: malformed JSON"; FAIL=$((FAIL+1)); fi

# PR #861 B-3 — force-staging: .worktreeinclude copies backend/.env and web/.env into every
# worktree, and `add -f` would stage one for Land to commit into a public repo.
FORCE='force-staging ignored files is not allowed'
assert_deny_msg "B-3: git add -f backend/.env"           $W 'git add -f backend/.env' "$FORCE"
assert_deny_msg "B-3: git add --force ."                 $W 'git add --force .' "$FORCE"
assert_deny_msg "B-3: git -C /tmp/wt add -fA"            $W 'git -C /tmp/wt add -fA' "$FORCE"
assert_deny_msg "B-3: git mv -f a b"                     $W 'git mv -f a b' "$FORCE"
assert_deny_msg "B-3: git rm -f x"                       $W 'git rm -f x' "$FORCE"
assert_deny_msg "B-3: git add -nf (bundle holding f)"    $W 'git add -nf backend/.env' "$FORCE"
assert_deny_msg "B-3: git add --forc (prefix of --force)" $W 'git add --forc backend/.env' "$FORCE"
assert_deny_msg "B-3: verifier git add -f too"           todo-verifier '/usr/bin/git -C /tmp/wt add -f web/.env' "$FORCE"
assert_allow "B-3: git add -A"                           $W 'git add -A'
assert_allow "B-3: an f in a file name is fine"          $W 'git add -- file-f.txt'
assert_allow "B-3: a path named -f after -- is fine"     $W 'git add -- -f'
assert_allow "B-3: git rm --cached x"                    $W 'git rm --cached x'
assert_allow "B-3: /usr/bin/git -C WT add -A"            $W '/usr/bin/git -C /tmp/wt add -A'
assert_allow "B-3: an unguarded caller may still add -f" general-purpose 'git add -f x'

# K10 — a missing script fails open (exit 0, no output) instead of blocking every Bash call
# (a TMPDIR template, because the Bash sandbox denies mktemp's default /var/folders)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/guard-todo-worker-git.XXXXXX") || TMP=""
[ -n "$TMP" ] && trap 'rm -rf "$TMP"' EXIT
RC=1; OUT="(no temp dir)"
if [ -n "$TMP" ] && mkdir -p "$TMP/.claude/hooks" && cp "$HOOK" "$TMP/.claude/hooks/"; then
  EV=$(event $W 'git push')  # a here-string, so the hook's own exit code is what RC sees
  OUT=$(bash "$TMP/.claude/hooks/guard-todo-worker-git.sh" <<< "$EV" 2>/dev/null); RC=$?
fi
if [ -z "$OUT" ] && [ $RC -eq 0 ]; then
  echo "PASS: K10: missing script fails open"; PASS=$((PASS+1))
else
  echo "FAIL: K10: missing script fails open (rc=$RC, out=$OUT)"; FAIL=$((FAIL+1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
