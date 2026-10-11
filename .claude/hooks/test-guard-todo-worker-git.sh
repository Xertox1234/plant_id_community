#!/usr/bin/env bash
# Tests for guard-todo-worker-git.sh — run from anywhere.
# The guard limits the todo sweep's agents' Bash calls (todo-worker, todo-verifier,
# todo-reviewer and the review agents todo-review dispatches) to limited git (spec §4.1). The cases that matter are the disguises: wrappers, absolute
# paths, compound commands, bash -c, $(...), a second line — and the harmless
# mention of "git commit" inside a grep, which must still be allowed.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/guard-todo-worker-git.sh"
PASS=0; FAIL=0
# Todo 496 round 3: the guard reads the top-level shell from $SHELL; the agents' shell here is zsh
# (CI runners default to bash). Cases that need another shell set it per call (shell_raw).
export SHELL=/bin/zsh

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
assert_allow "another agent type"                    general-purpose 'git push'

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
assert_raw   "K10: other agent, string tool_input"   allow '{"agent_type": "general-purpose", "tool_input": "git push"}'
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
assert_allow "other agent: unparseable quoting"      general-purpose 'git add "a.py'

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

# Todo 468 m7 — a guarded agent that confuses MAIN with WT must not stage into the owner's main
# checkout (its .git is a directory; a linked worktree's .git is a file). Reads stay allowed.
R=$(mktemp -d "${TMPDIR:-/tmp}/guard-main.XXXXXX") || R=""
if [ -n "$R" ] && git init -q "$R/main" && git -C "$R/main" -c user.email=t@t -c user.name=t commit -q --allow-empty -m i \
   && git -C "$R/main" worktree add -q -b wt-guard "$R/wt" 2>/dev/null && mkdir -p "$R/main/backend"; then
  MAIN_MSG='main checkout'
  cwd_event() {  # agent cwd command
    python3 -c 'import json, sys; print(json.dumps({"agent_type": sys.argv[1], "cwd": sys.argv[2], "tool_input": {"command": sys.argv[3]}}))' "$1" "$2" "$3"
  }
  assert_deny_msg "m7: git -C MAIN add -A"                 $W "/usr/bin/git -C $R/main add -A" "$MAIN_MSG"
  assert_deny_msg "m7: git -C MAIN mv a b"                 $W "git -C $R/main mv a b" "$MAIN_MSG"
  assert_deny_msg "m7: git -C MAIN rm --cached x"          $W "git -C $R/main rm --cached x" "$MAIN_MSG"
  assert_deny_msg "m7: git -C MAIN/backend add x"          $W "git -C $R/main/backend add x" "$MAIN_MSG"
  assert_deny_msg "m7: --work-tree=MAIN add"               $W "git --work-tree=$R/main add -A" "$MAIN_MSG"
  assert_deny_msg "m7: verifier git -C MAIN add"           todo-verifier "git -C $R/main add x" "$MAIN_MSG"
  assert_allow    "m7: git -C WT add -A"                   $W "/usr/bin/git -C $R/wt add -A"
  assert_allow    "m7: git -C MAIN status (a read)"        $W "git -C $R/main status --porcelain"
  assert_allow    "m7: git -C MAIN show (a read)"          $W "git -C $R/main show HEAD:x"
  assert_raw "m7: a bare git add with cwd MAIN" deny "$(cwd_event $W "$R/main" 'git add -A')"
  assert_raw "m7: a relative -C resolving to MAIN" deny "$(cwd_event $W "$R" 'git -C main add -A')"
  assert_raw "m7: a bare git add with cwd WT" allow "$(cwd_event $W "$R/wt" 'git add -A')"
  assert_raw "m7: a relative -C into WT from MAIN's cwd" allow "$(cwd_event $W "$R/main" "git -C $R/wt add -A")"
  # PR #872 round 1: retry and repair workers run from the main session's cwd (often MAIN) and may cd
  # into WT or name it through a variable; the guard cannot tell the directory, so it must not deny.
  assert_raw "PR #872: cd WT && git add -A from MAIN's cwd" allow "$(cwd_event $W "$R/main" "cd '$R/wt' && git add -A")"
  assert_raw "PR #872: (cd WT && git add -A) from MAIN's cwd" allow "$(cwd_event $W "$R/main" "(cd '$R/wt' && git add -A)")"
  assert_raw "PR #872: git -C \"\$WT\" add -A from MAIN's cwd" allow \
    "$(cwd_event $W "$R/main" "WT='$R/wt'; /usr/bin/git -C \"\$WT\" add -A")"
  assert_raw "PR #872: a literal -C MAIN is still denied after a cd" deny \
    "$(cwd_event $W "$R/wt" "cd /tmp && git -C $R/main add -A")"
  # Todo 468: a worker that deletes the .env rule from .gitignore cannot then stage the copied-in .env.
  printf 'backend/.env\nweb/.env\n' > "$R/wt/.worktreeinclude"
  printf 'backend/.env\nweb/.env\n' > "$R/wt/.gitignore"
  mkdir -p "$R/wt/backend" && echo 'SECRET_KEY=fake' > "$R/wt/backend/.env"  # pragma: allowlist secret
  assert_allow    "468: git add -A while the copied-in .env is still ignored" $W "git -C $R/wt add -A"
  printf 'web/.env\n' > "$R/wt/.gitignore"
  assert_deny_msg "468: git add -A after .gitignore stopped ignoring backend/.env" $W "git -C $R/wt add -A" \
    "backend/.env"
  assert_raw "468: the same from the worktree's own cwd" deny "$(cwd_event $W "$R/wt" 'git add .')"
  # Todo 477 round-2 note: after a cd into the worktree, the unignored-.env check still runs.
  assert_raw "477: the .env check still runs after a cd into the worktree" deny \
    "$(cwd_event $W "$R/main" "cd $R/wt && git add -A")"

  # Todo 477 finding 1: every way into the main checkout's index is checked.
  printf 'backend/.env\nweb/.env\n' > "$R/wt/.gitignore"
  assert_deny_msg "477: -C MAIN with --work-tree elsewhere stages into MAIN's index" $W \
    "git -C $R/main --work-tree=$R/wt add -A" "$MAIN_MSG"
  assert_deny_msg "477: --work-tree MAIN (separate value) from WT's -C"  $W "git -C $R/wt --work-tree $R/main add -A" "$MAIN_MSG"
  assert_deny_msg "477: a GIT_DIR prefix"                 $W "GIT_DIR=$R/main/.git git -C $R/wt add -A" "GIT_DIR"
  assert_deny_msg "477: a GIT_WORK_TREE prefix"           $W "GIT_WORK_TREE=$R/main git add -A" "GIT_WORK_TREE"
  assert_deny_msg "477: GIT_DIR through env"              $W "env GIT_DIR=$R/main/.git git add -A" "GIT_DIR"
  assert_deny_msg "477: an exported GIT_DIR"              $W "export GIT_DIR=$R/main/.git; git add -A" "GIT_DIR"
  assert_raw "477: a git-add binary with cwd MAIN" deny "$(cwd_event $W "$R/main" 'git-add -A')"
  assert_raw "477: a git-add binary with cwd WT" allow "$(cwd_event $W "$R/wt" 'git-add -A')"
  assert_raw "477: cd MAIN && git add from WT's cwd" deny "$(cwd_event $W "$R/wt" "cd $R/main && git add -A")"
  assert_raw "477: cd into MAIN/backend, then git add" deny "$(cwd_event $W "$R/wt" "cd $R/main/backend; git add x")"
  assert_raw "477: a relative cd from WT up into MAIN" deny "$(cwd_event $W "$R/wt" 'cd ../main && git add -A')"
  assert_raw "477: a cd inside ( ) does not move the next command" allow \
    "$(cwd_event $W "$R/wt" "(cd $R/main && git status); git add -A")"
  assert_raw "477: a cd inside \$( ) does not move the next command" allow \
    "$(cwd_event $W "$R/wt" "echo \$(cd $R/main) && git add -A")"
  assert_raw "477: a cd in a pipeline stage does not move the next command" allow \
    "$(cwd_event $W "$R/wt" "cd $R/main | cat; git add -A")"
  assert_raw "477: bash -c with a cd into MAIN" deny "$(cwd_event $W "$R/wt" "bash -c 'cd $R/main && git add -A'")"
  assert_raw "477: eval of a cd moves this shell" deny "$(cwd_event $W "$R/wt" "eval cd $R/main; git add -A")"
  assert_raw "477: a cd to a directory built at runtime is not checked" allow \
    "$(cwd_event $W "$R/main" "cd \"\$WT\" && git add -A")"
  assert_raw "477: an absolute -C after an unknown one is checked" deny \
    "$(cwd_event $W "$R/wt" "git -C \"\$WT\" -C $R/main add -A")"
  # The pilot layout: the sweep's main root is itself a linked worktree; its run file marks it.
  if git -C "$R/main" worktree add -q -b pilot-guard "$R/pilot" 2>/dev/null && mkdir -p "$R/pilot/todos"; then
    assert_allow    "477: a linked worktree without a run file is not a main checkout" $W "git -C $R/pilot add -A"
    : > "$R/pilot/todos/.sweep-run-2026-09-28-0000.json"
    assert_deny_msg "477: the pilot main root (linked, holds the run file) is a main checkout" $W \
      "git -C $R/pilot add -A" "$MAIN_MSG"
    assert_allow    "477: a worker worktree beside it is still fine" $W "git -C $R/wt add -A"
  else
    echo "FAIL: 477 pilot setup"; FAIL=$((FAIL+1))
  fi
  # Todo 477 finding 2: a TRACKED file that .worktreeinclude lists is ordinary content.
  printf 'backend/.env\n' > "$R/wt/.gitignore"
  mkdir -p "$R/wt/web" && echo 'VITE_API_URL=http://x' > "$R/wt/web/.env"
  git -C "$R/wt" add web/.env
  assert_allow "477: a tracked, not-ignored .worktreeinclude entry does not block staging" $W "git -C $R/wt add -A"
  git -C "$R/wt" rm -q --cached web/.env
  assert_deny_msg "477: the same file untracked is still refused" $W "git -C $R/wt add -A" "web/.env"

  # Todo 496 — routes into MAIN that PR #880's review rounds 2 and 3 found allowed.
  printf 'backend/.env\nweb/.env\n' > "$R/wt/.gitignore"
  # Finding 1: env -C / --chdir and sudo -D run the command in another directory.
  assert_raw "496.1: env -C MAIN git add" deny "$(cwd_event $W "$R/wt" "env -C $R/main git add -A")"
  assert_raw "496.1: env --chdir=MAIN git add" deny "$(cwd_event $W "$R/wt" "env --chdir=$R/main git add x")"
  assert_raw "496.1: env -iC MAIN (bundled)" deny "$(cwd_event $W "$R/wt" "/usr/bin/env -iC $R/main git add x")"
  assert_raw "496.1: sudo -D MAIN git add" deny "$(cwd_event $W "$R/wt" "sudo -D $R/main git add x")"
  assert_raw "496.1: env -C WT git add is fine" allow "$(cwd_event $W "$R/main" "env -C $R/wt git add -A")"
  assert_raw "496.1: env -C moves only its own command" allow \
    "$(cwd_event $W "$R/wt" "env -C $R/main true; git add -A")"
  assert_raw "496.1: command cd MAIN still moves this shell" deny \
    "$(cwd_event $W "$R/wt" "command cd $R/main; git add -A")"
  # Finding 2: zsh runs a pipeline's last stage in the current shell, so its cd sticks.
  assert_raw "496.2: a cd in the last pipeline stage sticks (zsh)" deny \
    "$(cwd_event $W "$R/wt" "true | cd $R/main; git add -A")"
  assert_raw "496.2: a backgrounded last stage does not" allow \
    "$(cwd_event $W "$R/wt" "true | cd $R/main & git add -A")"
  # Round-1 repair: bash/sh/dash run every pipeline stage in a subshell, so in a `bash -c` body the cd is undone.
  assert_raw "496.2r: bash -c 'true | cd WT; git add' from MAIN runs in MAIN" deny \
    "$(cwd_event $W "$R/main" "bash -c 'true | cd $R/wt; git add -A'")"
  assert_raw "496.2r: sh -c 'true | cd WT; git add' from MAIN runs in MAIN" deny \
    "$(cwd_event $W "$R/main" "sh -c 'true | cd $R/wt; git add -A'")"
  assert_raw "496.2r: dash -c 'true | cd WT; git add' from MAIN runs in MAIN" deny \
    "$(cwd_event $W "$R/main" "dash -c 'true | cd $R/wt; git add -A'")"
  assert_raw "496.2r: bash -c 'true | cd MAIN; git add' from WT runs in WT" allow \
    "$(cwd_event $W "$R/wt" "bash -c 'true | cd $R/main; git add -A'")"
  # zsh -c and ksh (ksh93) keep the last stage in the current shell, like the top level.
  assert_raw "496.2r: zsh -c 'true | cd MAIN; git add' sticks" deny \
    "$(cwd_event $W "$R/wt" "zsh -c 'true | cd $R/main; git add -A'")"
  assert_raw "496.2r: ksh -c 'true | cd MAIN; git add' sticks" deny \
    "$(cwd_event $W "$R/wt" "ksh -c 'true | cd $R/main; git add -A'")"
  assert_raw "496.2r: a \$(...) in a bash -c body is bash too" deny \
    "$(cwd_event $W "$R/main" "bash -c 'echo \$(true | cd $R/wt; git add -A)'")"
  # Finding 3: a $(...) runs after the cd before it.
  assert_raw "496.3: cd MAIN && echo \$(git add -A)" deny "$(cwd_event $W "$R/wt" "cd $R/main && echo \$(git add -A)")"
  assert_raw "496.3: cd MAIN; x=\$(git add -A)" deny "$(cwd_event $W "$R/wt" "cd $R/main; x=\$(git add -A)")"
  assert_raw "496.3: cd MAIN, then a heredoc body's \$(git add)" deny \
    "$(cwd_event $W "$R/wt" "$(printf 'cd %s\ncat <<EOF\n$(git add -A)\nEOF' "$R/main")")"
  assert_raw "496.3: a case word's \$(...) after a cd" deny \
    "$(cwd_event $W "$R/wt" "cd $R/main; case \$(git add -A) in *) ;; esac")"
  assert_raw "496.3: \$(git add) before a cd runs in WT" allow \
    "$(cwd_event $W "$R/wt" "echo \$(git add -A) && cd $R/main")"
  # Finding 4: ~ and ~/... are the home directory (HOME points at the fixture here).
  OLD_HOME=$HOME; export HOME="$R"
  assert_raw "496.4: git -C ~/main add" deny "$(cwd_event $W "$R/wt" 'git -C ~/main add x')"
  assert_raw "496.4: cd ~/main && git add" deny "$(cwd_event $W "$R/wt" 'cd ~/main && git add x')"
  assert_raw "496.4: git -C ~/wt add is fine" allow "$(cwd_event $W "$R/main" 'git -C ~/wt add x')"
  export HOME="$OLD_HOME"

  # Todo 496 round 3 (owner-approved) — the routes round 2 found still open.
  # B: env -S splits its string into words that env parses as its own options, so -C inside it moves the command.
  assert_raw "496.B: env -S '-C MAIN git add -A' from WT" deny "$(cwd_event $W "$R/wt" "env -S '-C $R/main git add -A'")"
  assert_raw "496.B: env -S'-C MAIN' git add -A (glued) from WT" deny "$(cwd_event $W "$R/wt" "env -S'-C $R/main' git add -A")"
  assert_raw "496.B: env -iS '-C MAIN git add x' from WT" deny "$(cwd_event $W "$R/wt" "env -iS '-C $R/main git add x'")"
  assert_raw "496.B: env -S '-C WT git add -A' from MAIN is fine" allow "$(cwd_event $W "$R/main" "env -S '-C $R/wt git add -A'")"
  # C: macOS env -P altpath takes a value.
  assert_raw "496.C: env -P /x -C MAIN git add -A from WT" deny "$(cwd_event $W "$R/wt" "env -P /x -C $R/main git add -A")"
  assert_raw "496.C: env -P /usr/bin git add -A from WT is fine" allow "$(cwd_event $W "$R/wt" "env -P /usr/bin git add -A")"
  # D: bash with lastpipe keeps a pipeline's last stage in the shell, so its cd sticks.
  assert_raw "496.D: bash -c 'shopt -s lastpipe; true | cd MAIN; git add -A' from WT" deny \
    "$(cwd_event $W "$R/wt" "bash -c 'shopt -s lastpipe; true | cd $R/main; git add -A'")"
  assert_raw "496.D: bash -c 'set -o lastpipe; ...' from WT" deny \
    "$(cwd_event $W "$R/wt" "bash -c 'set -o lastpipe; true | cd $R/main; git add -A'")"
  assert_raw "496.D: shopt -s with a runtime operand counts as lastpipe" deny \
    "$(cwd_event $W "$R/wt" "bash -c 'shopt -s \$o; true | cd $R/main; git add -A'")"
  assert_raw "496.D: bash -O lastpipe -c ... from WT" deny \
    "$(cwd_event $W "$R/wt" "bash -O lastpipe -c 'true | cd $R/main; git add -A'")"
  assert_raw "496.D: shopt -s extglob does not make the last stage stick" allow \
    "$(cwd_event $W "$R/wt" "bash -c 'shopt -s extglob; true | cd $R/main; git add -A'")"
  assert_raw "496.D: lastpipe in one bash -c body does not leak into the next" allow \
    "$(cwd_event $W "$R/wt" "bash -c 'shopt -s lastpipe'; bash -c 'true | cd $R/main; git add -A'")"
  # E: the top-level shell is \$SHELL's (zsh when unset); an unknown shell's piped cd fails closed.
  shell_raw() {  # name SHELL deny|allow event
    local out ok=0
    out=$(printf '%s' "$4" | SHELL="$2" bash "$HOOK" 2>/dev/null)
    if [ "$3" = deny ]; then grep -q '"permissionDecision": "deny"' <<< "$out" && ok=1
    else [ -z "$out" ] && ok=1; fi
    if [ $ok -eq 1 ]; then echo "PASS: $1"; PASS=$((PASS+1))
    else echo "FAIL: $1 (expected $3)"; echo "  got: $out"; FAIL=$((FAIL+1)); fi
  }
  shell_raw "496.E: SHELL=bash: a last-stage cd MAIN does not stick" /bin/bash allow \
    "$(cwd_event $W "$R/wt" "true | cd $R/main; git add -A")"
  shell_raw "496.E: SHELL=bash: a last-stage cd WT from MAIN leaves git in MAIN" /bin/bash deny \
    "$(cwd_event $W "$R/main" "true | cd $R/wt; git add -A")"
  shell_raw "496.E: SHELL=bash with shopt -s lastpipe sticks" /bin/bash deny \
    "$(cwd_event $W "$R/wt" "shopt -s lastpipe; true | cd $R/main; git add -A")"
  shell_raw "496.E: SHELL unset is zsh: the cd sticks" "" deny \
    "$(cwd_event $W "$R/wt" "true | cd $R/main; git add -A")"
  shell_raw "496.E: an unknown SHELL, cd MAIN in the last stage from WT" /usr/local/bin/nu deny \
    "$(cwd_event $W "$R/wt" "true | cd $R/main; git add -A")"
  shell_raw "496.E: an unknown SHELL, cd WT in the last stage from MAIN" /usr/local/bin/nu deny \
    "$(cwd_event $W "$R/main" "true | cd $R/wt; git add -A")"
  shell_raw "496.E: an unknown SHELL, cd elsewhere from WT is unknown (not checked)" /usr/local/bin/nu allow \
    "$(cwd_event $W "$R/wt" "true | cd /tmp; git add -A")"
  # J: sudo and env take an unambiguous prefix of a long option.
  assert_raw "496.J: sudo --chd=MAIN git add -A from WT" deny "$(cwd_event $W "$R/wt" "sudo --chd=$R/main git add -A")"
  assert_raw "496.J: sudo --chdi MAIN git add -A from WT" deny "$(cwd_event $W "$R/wt" "sudo --chdi $R/main git add -A")"
  assert_raw "496.J: env --chd=MAIN git add -A from WT" deny "$(cwd_event $W "$R/wt" "env --chd=$R/main git add -A")"
  assert_raw "496.J: sudo --chd=WT git add -A from MAIN is fine" allow "$(cwd_event $W "$R/main" "sudo --chd=$R/wt git add -A")"
  # K: a value glued onto a short option is cut at the same index as the option's letters.
  assert_raw "496.K: env -C<MAIN> (glued) from WT" deny "$(cwd_event $W "$R/wt" "env -C$R/main git add -A")"
  assert_raw "496.K: sudo -D<MAIN> (glued) from WT" deny "$(cwd_event $W "$R/wt" "sudo -D$R/main git add x")"
  assert_raw "496.K: env -iC<MAIN> (bundled, glued) from WT" deny "$(cwd_event $W "$R/wt" "env -iC$R/main git add x")"
  OLD_HOME=$HOME; export HOME="$R"
  # A glued -C~/main is not tilde-expanded by the shell: env gets a literal ~ (and fails), not HOME/main.
  assert_raw "496.K: env -C~/main (glued, no tilde expansion) is not HOME/main" allow \
    "$(cwd_event $W "$R/wt" 'env -C~/main git add -A')"
  export HOME="$OLD_HOME"
  assert_raw "496.ordinary: set -euo pipefail, then git -C WT add -A" allow \
    "$(cwd_event $W "$R/wt" "set -euo pipefail; /usr/bin/git -C $R/wt add -A && /usr/bin/git -C $R/wt diff --cached --stat")"

  # Todo 584 — follow-ups from PR #1023 (todo 496).
  # Finding 1: a trap action (and a mapfile -C callback) runs later, in whatever directory the shell is in then.
  assert_raw "584.1: trap 'git add -A' EXIT; cd MAIN from WT" deny \
    "$(cwd_event $W "$R/wt" "trap 'git add -A' EXIT; cd $R/main")"
  assert_raw "584.1: trap 'cd MAIN' DEBUG; git add -A from WT" deny \
    "$(cwd_event $W "$R/wt" "trap 'cd $R/main' DEBUG; git add -A")"
  assert_raw "584.1: trap 'cd MAIN' EXIT (a cd in a trap action)" deny \
    "$(cwd_event $W "$R/wt" "trap 'cd $R/main' EXIT; git status")"
  assert_raw "584.1: trap 'git-add -A' EXIT (a git-add binary)" deny \
    "$(cwd_event $W "$R/wt" "trap 'git-add -A' EXIT")"
  assert_deny  "584.1: trap 'true' ERR"                    $W "trap 'true' ERR; git status"
  assert_deny  "584.1: trap 'true' ZERR (zsh)"             $W "trap 'true' ZERR; git status"
  assert_deny  "584.1: trap 'true' SIGDEBUG"               $W "trap 'true' SIGDEBUG; git status"
  assert_raw "584.1: mapfile -C 'cd MAIN' callback, then git add -A from WT" deny \
    "$(cwd_event $W "$R/wt" "mapfile -C 'cd $R/main' -c 1 arr < f; git add -A")"
  assert_raw "584.1: trap 'git -C WT add -A' EXIT names the worktree" allow \
    "$(cwd_event $W "$R/main" "trap '/usr/bin/git -C $R/wt add -A' EXIT")"
  assert_raw "584.1: trap - DEBUG (a reset) and trap '' ERR (ignore)" allow \
    "$(cwd_event $W "$R/wt" "trap - DEBUG; trap '' ERR; git add -A")"
  # Finding 2: shopt -u lastpipe clears it; set -o lastpipe is not a bash option (it changes nothing), so unknown.
  assert_raw "584.2: bash -c 'shopt -s lastpipe; shopt -u lastpipe; true | cd WT; git add' from MAIN" deny \
    "$(cwd_event $W "$R/main" "bash -c 'shopt -s lastpipe; shopt -u lastpipe; true | cd $R/wt; git add -A'")"
  assert_raw "584.2: bash -c 'shopt -s lastpipe; shopt -u lastpipe; true | cd MAIN; git add' from WT" allow \
    "$(cwd_event $W "$R/wt" "bash -c 'shopt -s lastpipe; shopt -u lastpipe; true | cd $R/main; git add -A'")"
  assert_raw "584.2: bash -c 'set -o lastpipe; true | cd WT; git add' from MAIN" deny \
    "$(cwd_event $W "$R/main" "bash -c 'set -o lastpipe; true | cd $R/wt; git add -A'")"
  assert_raw "584.2: a runtime shopt -u operand after lastpipe, from MAIN" deny \
    "$(cwd_event $W "$R/main" "bash -c 'shopt -s lastpipe; shopt -u \$o; true | cd $R/wt; git add -A'")"
  assert_raw "584.2: bash -O lastpipe +O lastpipe -c ... from WT" allow \
    "$(cwd_event $W "$R/wt" "bash -O lastpipe +O lastpipe -c 'true | cd $R/main; git add -A'")"
  # Finding 3: bash's keyword option exports every NAME=value argument, so it is refused like allexport.
  assert_deny  "584.3: set -k"                             $W 'set -k; git log GIT_PAGER=/tmp/x'
  assert_deny  "584.3: set -ek (bundled)"                  $W 'set -ek; git status'
  assert_deny  "584.3: set -o keyword"                     $W 'set -o keyword; git status'
  assert_deny  "584.3: shopt -so keyword"                  $W 'shopt -so keyword'
  assert_deny  "584.3: setopt keyword"                     $W 'setopt keyword'
  assert_deny  "584.3: bash -k -c"                         $W "bash -k -c 'git log GIT_PAGER=/tmp/x'"
  assert_deny  "584.3: bash -o keyword -c"                 $W "bash -o keyword -c 'git status'"
  assert_deny  "584.3: zsh --keyword -c"                   $W "zsh --keyword -c 'git status'"
  assert_deny  "584.3: emulate -o keyword sh"              $W 'emulate -o keyword sh'
  # Finding 4 (owner decision: track the cwd through the piped stage): bash runs a piped { }/if/while/( ) as
  # one subshell, so a cd inside it holds for the rest of that stage and is undone at the stage's end.
  assert_raw "584.4: bash -c 'true | { cd MAIN; git add -A; }' from WT" deny \
    "$(cwd_event $W "$R/wt" "bash -c 'true | { cd $R/main; git add -A; }'")"
  assert_raw "584.4: bash -c 'true | if true; then cd MAIN; git add -A; fi' from WT" deny \
    "$(cwd_event $W "$R/wt" "bash -c 'true | if true; then cd $R/main; git add -A; fi'")"
  assert_raw "584.4: bash -c 'true | while true; do cd MAIN; git add -A; break; done' from WT" deny \
    "$(cwd_event $W "$R/wt" "bash -c 'true | while true; do cd $R/main; git add -A; break; done'")"
  assert_raw "584.4: bash -c 'true | ( cd MAIN; git add -A )' from WT" deny \
    "$(cwd_event $W "$R/wt" "bash -c 'true | ( cd $R/main; git add -A )'")"
  assert_raw "584.4: bash -c 'true | case x in *) cd MAIN; git add -A;; esac' from WT" deny \
    "$(cwd_event $W "$R/wt" "bash -c 'true | case x in *) cd $R/main; git add -A;; esac'")"
  assert_raw "584.4: bash -c 'true | { cd MAIN; }; git add -A' from WT (undone at the stage end)" allow \
    "$(cwd_event $W "$R/wt" "bash -c 'true | { cd $R/main; }; git add -A'")"
  assert_raw "584.4: bash -c 'true | { cd WT; }; git add -A' from MAIN" deny \
    "$(cwd_event $W "$R/main" "bash -c 'true | { cd $R/wt; }; git add -A'")"
  assert_raw "584.4: a first-stage { cd WT; } | cat, then git add -A from MAIN" deny \
    "$(cwd_event $W "$R/main" "{ cd $R/wt; } | cat; git add -A")"
  assert_raw "584.4: bash -c 'shopt -s lastpipe; true | { cd MAIN; }; git add -A' from WT" deny \
    "$(cwd_event $W "$R/wt" "bash -c 'shopt -s lastpipe; true | { cd $R/main; }; git add -A'")"
  assert_raw "584.4: zsh: a last-stage { cd MAIN; } sticks" deny \
    "$(cwd_event $W "$R/wt" "true | { cd $R/main; }; git add -A")"
  assert_raw "584.4: zsh: a middle-stage { cd MAIN; } does not" allow \
    "$(cwd_event $W "$R/wt" "true | { cd $R/main; } | cat; git add -A")"
  assert_raw "584.4: a nested pipeline inside a piped group still restores its own stage" allow \
    "$(cwd_event $W "$R/wt" "bash -c 'true | { cd $R/main | cat; git add -A; }'")"
  shell_raw "584.4: SHELL=bash: true | { cd MAIN; git add -A; } from WT" /bin/bash deny \
    "$(cwd_event $W "$R/wt" "true | { cd $R/main; git add -A; }")"
  shell_raw "584.4: SHELL=bash: true | { cd WT; }; git add -A from MAIN" /bin/bash deny \
    "$(cwd_event $W "$R/main" "true | { cd $R/wt; }; git add -A")"
  shell_raw "584.4: SHELL=bash: true | { cd MAIN; }; git add -A from WT" /bin/bash allow \
    "$(cwd_event $W "$R/wt" "true | { cd $R/main; }; git add -A")"
  # Finding 5: a function body runs when the function is called, not where it is defined.
  assert_raw "584.5: f() { cd MAIN; }; cd WT; f; git add -A" deny \
    "$(cwd_event $W "$R/wt" "f() { cd $R/main; }; cd $R/wt; f; git add -A")"
  assert_raw "584.5: function f { cd MAIN; }" deny \
    "$(cwd_event $W "$R/wt" "function f { cd $R/main; }; f; git add -A")"
  assert_raw "584.5: f() ( cd MAIN; git add -A )" deny \
    "$(cwd_event $W "$R/wt" "f() ( cd $R/main; git add -A ); f")"
  assert_raw "584.5: f(){ git add -A; }; cd MAIN; f (a bare git add in a body)" deny \
    "$(cwd_event $W "$R/wt" "f(){ git add -A; }; cd $R/main; f")"
  assert_raw "584.5: a body that names the worktree is fine" allow \
    "$(cwd_event $W "$R/main" "f() { /usr/bin/git -C $R/wt add -A; }; f")"
  assert_raw "584.5: a body without cd or staging, then git add -A" allow \
    "$(cwd_event $W "$R/wt" "f() { echo hi; git status; }; f; git add -A")"
  assert_raw "584.5: a cd after the body is followed as usual" deny \
    "$(cwd_event $W "$R/wt" "f() { echo hi; }; cd $R/main; git add -A")"
  # Finding 6: the bash top-level model (SHELL=/bin/bash, the CI default) for the 496.2 and brace-group cases.
  shell_raw "584.6: SHELL=bash: a backgrounded last stage" /bin/bash allow \
    "$(cwd_event $W "$R/wt" "true | cd $R/main & git add -A")"
  shell_raw "584.6: SHELL=bash: a cd in a first stage does not move the next command" /bin/bash allow \
    "$(cwd_event $W "$R/wt" "cd $R/main | cat; git add -A")"
  shell_raw "584.6: SHELL=bash: bash -c 'true | cd WT; git add' from MAIN" /bin/bash deny \
    "$(cwd_event $W "$R/main" "bash -c 'true | cd $R/wt; git add -A'")"
  shell_raw "584.6: SHELL=bash: a brace group { git push; }" /bin/bash deny \
    "$(cwd_event $W "$R/wt" "{ git push; }")"
  shell_raw "584.6: SHELL=bash: { cd MAIN; git add -A; } from WT" /bin/bash deny \
    "$(cwd_event $W "$R/wt" "{ cd $R/main; git add -A; }")"
  shell_raw "584.6: SHELL=bash: { cd MAIN; }; git add -A from WT (a group is not a subshell)" /bin/bash deny \
    "$(cwd_event $W "$R/wt" "{ cd $R/main; }; git add -A")"
else
  echo "FAIL: m7 setup (could not build a main checkout and a worktree)"; FAIL=$((FAIL+1))
fi
[ -n "$R" ] && rm -rf "$R"

# Todo 468 m8 — review-stage reviewers run as todo-reviewer: read-only git, no gh.
V=todo-reviewer
assert_allow "m8: reviewer git diff origin/main...HEAD"  $V "/usr/bin/git -C '/wt/g1' diff origin/main...HEAD"
assert_allow "m8: reviewer git log / show / ls-files"    $V 'git log -3 && git show HEAD:a.py && git ls-files'
assert_deny  "m8: reviewer git add"                      $V 'git add -A'
assert_deny  "m8: reviewer git commit"                   $V 'git commit -m x'
assert_deny  "m8: reviewer git push"                     $V 'git push'
assert_deny  "m8: reviewer git fetch"                    $V 'git fetch origin'
assert_deny  "m8: reviewer gh"                           $V 'gh pr view 1'

# Todo 472 — todo-review dispatches the orchestrator and domain reviewers: same read-only limit.
# Todo 478: every one of them, read from the guard itself (the loop used to name 4 of the 9).
GUARD_DIR="$(cd "$(dirname "$0")/../.." && pwd)/scripts/todos"
REVIEWERS=$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import worker_git_guard as g; print(" ".join(g.REVIEW_AGENTS))' "$GUARD_DIR")
if [ "$(wc -w <<< "$REVIEWERS" | tr -d ' ')" = 9 ]; then
  echo "PASS: 478: the guard names 9 review agents"; PASS=$((PASS+1))
else
  echo "FAIL: 478: the guard names 9 review agents (got: $REVIEWERS)"; FAIL=$((FAIL+1))
fi
for V in $REVIEWERS; do
  assert_allow "472: $V git diff in the worktree"   $V "/usr/bin/git -C '/wt/g1' diff origin/main...HEAD --name-only"
  assert_allow "472: $V git show / rev-parse"       $V 'git show HEAD:a.py && git rev-parse --short HEAD'
  assert_deny  "472: $V git stash"                  $V 'git stash'
  assert_deny  "472: $V git commit"                 $V 'git commit -m x'
  assert_deny  "472: $V gh pr comment"              $V 'gh pr comment 1 --body x'
done

# Todo 478 finding 5 — guard gaps: git grep -O and GIT_* prefixes run a program through an allowed read.
V=todo-reviewer
assert_deny  "478: git grep -O<cmd>"                     $V 'git grep -Ovim foo'
assert_deny  "478: git grep -O in a short bundle"        $V 'git grep -lO foo'
assert_deny  "478: git grep --open-files-in-pager"       $V 'git grep --open-files-in-pager=vim foo'
assert_deny  "478: git grep --open (a prefix)"           $V 'git grep --open foo'
assert_allow "478: a pattern holding O after -e is a value" $V "git grep -l -e 'Oops' -e -O -- '*.py'"
assert_allow "478: the router's wagtail grep"            code-review-orchestrator \
  "/usr/bin/git -C '/wt/g1' grep -l -e 'import wagtail' -e 'from wagtail' -e 'from .models import.*Page' -- '*.py'"
assert_deny  "478: GIT_EXTERNAL_DIFF on diff"            $V 'GIT_EXTERNAL_DIFF=/tmp/x git diff'
assert_deny  "478: GIT_PAGER on log"                     $V 'GIT_PAGER=/tmp/x git log -p'
assert_deny  "478: GIT_PAGER through env"                $V 'env GIT_PAGER=/tmp/x git log'
assert_allow "478: another variable is fine"             $V 'LC_ALL=C git log --oneline -1'

# Todo 477 finding 3 — reviewers may read more of the history, and still never write refs.
assert_allow "477: reviewer cat-file / ls-tree / rev-list" $V 'git cat-file -p HEAD && git ls-tree HEAD && git rev-list -3 HEAD'
assert_allow "477: reviewer branch --show-current"       $V 'git branch --show-current'
assert_allow "477: reviewer branch -a / worktree list"   $V 'git branch -a && git worktree list'
assert_deny  "477: reviewer creating a branch"           $V 'git branch new-one'
assert_deny  "477: reviewer deleting a branch"           $V 'git branch -D main'
assert_deny  "477: reviewer worktree add"                $V 'git worktree add /tmp/x'
assert_deny  "477: reviewer cat-file --textconv"         $V 'git cat-file --textconv HEAD:a.py'
assert_deny  "477: a worker still may not list branches" $W 'git branch --show-current'

# Todo 496 finding 5 — a GIT_* variable set by a builtin other than NAME=value.
assert_deny_msg "496.5: read GIT_DIR, export GIT_DIR"   $W 'read GIT_DIR <<< /x/.git; export GIT_DIR; git add x' "GIT_DIR"
assert_deny_msg "496.5: export of a bare GIT_DIR"       $W 'export GIT_DIR; git add x' "GIT_DIR"
assert_deny_msg "496.5: printf -v GIT_DIR"              $W 'printf -v GIT_DIR %s /x/.git; git add x' "GIT_DIR"
assert_deny_msg "496.5: printf -vGIT_PAGER (glued)"     $V 'printf -vGIT_PAGER %s /tmp/x; git log' "GIT_PAGER"
assert_deny_msg "496.5: for GIT_DIR in ..."             $W 'for GIT_DIR in /x/.git; do git add x; done' "GIT_DIR"
assert_deny_msg "496.5: mapfile GIT_X"                  $W 'mapfile GIT_X < f' "GIT_X"
assert_deny_msg "496.5: a quoted export 'GIT_DIR=x'"    $W "export 'GIT_DIR=/x/.git'; git add x" "GIT_DIR"
assert_allow "496.5: read / printf -v / for of other names" $W 'read A <<< x; printf -v B %s y; for f in GIT_DIR; do echo $f; done; git status'
# Finding 6 — a 2-letter prefix reaches the dangerous option too (owner decision 2026-10-11).
assert_deny  "496.6: git grep --op=<cmd> (--open-files-in-pager)" $V 'git grep --op=vim x'
assert_deny  "496.6: git fetch --st (--stdin)"           $W 'echo main:main | git fetch --st origin'
assert_deny  "496.6: git cat-file --te (--textconv)"     $V 'git cat-file --te HEAD:a.py'
assert_deny  "496.6: git cat-file --fi (--filters)"      $V 'git cat-file --fi HEAD:a.py'
assert_deny  "496.6: git diff --ou (--output)"           $W 'git diff --ou=/tmp/x'
assert_allow "496.6: the exact --text is still a real option" $V 'git grep --text x && git diff --text'
assert_deny  "496.6r: git cat-file --t (one-letter prefix of --textconv)" $V 'git cat-file --t HEAD:a.py'
assert_deny  "496.6r: git diff --o=<file> (one-letter prefix of --output)" $W 'git diff --o=/tmp/x'
assert_allow "496.6r: ordinary diff/log/show/cat-file/grep options" $V 'git diff --stat && git log --oneline -n 3 && git show --name-only HEAD && git cat-file -t HEAD && git grep -n x'
assert_allow "496.6r: an ordinary git fetch" $W 'git fetch origin main'
# Finding 7 — rev-list hands unknown options to the diff parser, which opens --output.
assert_deny  "496.7: git rev-list --output"              $V 'git rev-list --output=/tmp/x HEAD'
assert_allow "496.7: git rev-list --count"               $V 'git rev-list --count HEAD'
# Finding 8 — git grep --textconv runs a configured driver program.
assert_deny  "496.8: git grep --textconv"                $V 'git grep --textconv x'

# Todo 496 round 3 (owner-approved) — A: env -S re-enters env's own option parser.
assert_deny  "496.A: env -iS 'git push'"                 $W "env -iS 'git push'"
assert_deny  "496.A: env -0S 'git commit -m x'"          $W "env -0S 'git commit -m x'"
assert_deny  "496.A: env -S '-i git push'"               $W "env -S '-i git push'"
assert_deny  "496.A: env -S '-u X -i git push'"          $W "env -S '-u X -i git push'"
assert_deny  "496.A: env --split-string='-i git push'"   $W "env --split-string='-i git push'"
assert_deny  "496.A: env --spl '-i git push' (abbreviated)" $W "env --spl '-i git push'"
assert_deny  "496.A: env -S'-i' git push (glued)"        $W "env -S'-i' git push"
assert_allow "496.A: env -iS 'git status'"               $W "env -iS 'git status'"
# C: macOS env -P altpath takes a value.
assert_deny  "496.C: env -P /usr/bin git commit -m x"    $W 'env -P /usr/bin git commit -m x'
# F: allexport, in every spelling, is refused; other shell options are not.
assert_deny  "496.F: set -a"                             $W 'set -a; git status'
assert_deny  "496.F: set -ea (bundled)"                  $W 'set -ea; git status'
assert_deny  "496.F: set -o allexport"                   $W 'set -o allexport; git status'
assert_deny  "496.F: setopt allexport"                   $W 'setopt allexport; git status'
assert_deny  "496.F: setopt all_export"                  $W 'setopt all_export'
assert_deny  "496.F: setopt ALL_EXPORT"                  $W 'setopt ALL_EXPORT'
assert_deny  "496.F: setopt AllExport"                   $W 'setopt AllExport'
assert_deny  "496.F: unsetopt no_all_export"             $W 'unsetopt no_all_export'
assert_deny  "496.F: setopt -m 'all*' (a pattern)"       $W "setopt -m 'all*'"
assert_deny  "496.F: set -o \$opt (built at runtime)"    $W 'set -o $opt'
assert_deny  "496.F: shopt -so allexport"                $W 'shopt -so allexport'
assert_deny  "496.F: bash -a -c"                         $W "bash -a -c 'git status'"
assert_deny  "496.F: bash -o allexport -c"               $W "bash -o allexport -c 'git status'"
assert_deny  "496.F: zsh --all-export -c"                $W "zsh --all-export -c 'git status'"
assert_deny  "496.F: emulate -o allexport zsh"           $W 'emulate -o allexport zsh'
assert_deny  "496.F: SHELLOPTS=allexport bash -c"        $W "SHELLOPTS=allexport bash -c 'git status'"
assert_deny  "496.F: env BASHOPTS=lastpipe bash -c"      $W "env BASHOPTS=lastpipe bash -c 'git status'"
assert_allow "496.F: set -e"                             $W 'set -e; git status'
assert_allow "496.F: set -euo pipefail"                  $W 'set -euo pipefail; git status'
assert_allow "496.F: set -o pipefail / set -x / set +a"  $W 'set -o pipefail; set -x; set +a; git status'
assert_allow "496.F: setopt extended_glob"               $W 'setopt extended_glob; git status'
assert_allow "496.F: set -- a b"                         $W 'set -- a b; git status'
assert_allow "496.F: bash -euo pipefail -c"              $W "bash -euo pipefail -c 'git status'"
# G: a GIT_* variable assigned inside an expansion or arithmetic.
assert_deny  "496.G: : \${GIT_DIR:=/x/.git}"             $W ': ${GIT_DIR:=/x/.git}; git add x'
assert_deny  "496.G: : \${GIT_DIR=/x/.git}"              $W ': ${GIT_DIR=/x/.git}; git add x'
assert_deny  "496.G: : \${GIT_DIR::=/x/.git} (zsh)"      $W ': ${GIT_DIR::=/x/.git}; git add x'
assert_deny  "496.G: echo \"\${GIT_PAGER:=cat}\""        $V 'echo "${GIT_PAGER:=/tmp/x}"; git log'
assert_deny  "496.G: case \${GIT_DIR:=x} in"             $W 'case ${GIT_DIR:=/x} in *) ;; esac; git add x'
assert_deny  "496.G: an unquoted heredoc body"           $W $'cat <<EOF\n${GIT_DIR:=/x/.git}\nEOF\ngit add x'
assert_deny  "496.G: zsh \${(P)n::=x}"                   $W 'n=GIT_DIR; : ${(P)n::=/x/.git}; git add x'
assert_deny  "496.G: \$((GIT_X=1))"                      $W ': $((GIT_X=1)); git status'
assert_deny  "496.G: (( GIT_X = 1 ))"                    $W '(( GIT_X = 1 )); git status'
assert_deny  "496.G: let GIT_X=1"                        $W 'let GIT_X=1; git status'
assert_allow "496.G: \${GIT_DIR:-default} only reads"    $W 'echo "${GIT_DIR:-unset}"; git status'
assert_allow "496.G: other arithmetic"                   $W 'x=$((1 + 2)); (( i = 1 )); echo $(( x == 3 )); git status'
assert_allow "496.G: grep for the text GIT_DIR="         $V "grep -n 'GIT_DIR=' scripts/todos/worker_git_guard.py"
# H: a variable name built at runtime, and namerefs to GIT_* names.
assert_deny  "496.H: p=GIT_; export \${p}DIR=x"          $W 'p=GIT_; export ${p}DIR=/x/.git; git add x'
assert_deny  "496.H: declare \"\${p}DIR=x\""             $W 'declare "${p}DIR=/x/.git"; git add x'
assert_deny  "496.H: export \"\$n\"=x"                   $W 'export "$n"=/x/.git; git add x'
assert_deny  "496.H: read -r \"\$n\""                    $W 'read -r "$n" <<< /x/.git; git add x'
assert_deny  "496.H: printf -v \"\$n\""                  $W 'printf -v "$n" %s /x/.git; git add x'
assert_deny  "496.H: getopts ab \"\$n\""                 $W 'getopts ab "$n"; git add x'
assert_deny  "496.H: declare -n r=GIT_DIR; export r=x"   $W 'declare -n r=GIT_DIR; export r=/x/.git; git add x'
assert_deny  "496.H: typeset -n r=GIT_DIR"               $W 'typeset -n r=GIT_DIR; r=/x/.git; git add x'
assert_deny  "496.H: local -n r=GIT_PAGER"               $V 'f(){ local -n r=GIT_PAGER; r=/tmp/x; git log; }; f'
assert_deny  "496.H: declare -n r; r=GIT_DIR (unset nameref)" $W 'declare -n r; r=GIT_DIR; r=/x/.git; git add x'
assert_deny  "496.H: ksh nameref r=GIT_DIR"              $W 'nameref r=GIT_DIR; r=/x/.git; git add x'
assert_deny  "496.H: integer GIT_X=1 (zsh)"              $W 'integer GIT_X=1'
assert_deny  "496.H: typeset GIT_DIR[1]=x (a subscript)" $W 'typeset GIT_DIR[1]=/x/.git'
assert_allow "496.H: export PATH=\"\$HOME/bin:\$PATH\"" $W 'export PATH="$HOME/bin:$PATH"; git status'
assert_allow "496.H: local x=\"\$(pwd)\" / declare -a"   $W 'f(){ local x="$(pwd)"; declare -a arr; }; f; git status'
assert_allow "496.H: declare -n r=OTHER"                 $W 'declare -n r=OTHER; git status'
assert_allow "496.H: read -r line / read -p \"\$P\" x"   $W 'read -r line <<< x; read -p "$P" x <<< y; git status'
assert_allow "496.H: getopts ab opt \"\$@\""             $W 'getopts ab opt "$@"; git status'
# I: every zsh loop variable, and read's NAME?prompt.
assert_deny  "496.I: for a GIT_DIR in x y"               $W 'for a GIT_DIR in x y; do git add x; done'
assert_deny  "496.I: for a GIT_DIR (x y) (zsh)"          $W 'for a GIT_DIR (x y) { git add x }'
assert_deny  "496.I: select a GIT_DIR in x"              $W 'select a GIT_DIR in x; do git add x; done'
assert_deny  "496.I: foreach GIT_DIR (x) (zsh)"          $W $'foreach GIT_DIR (/x/.git)\ngit add x\nend'
assert_deny  "496.I: read 'GIT_DIR?prompt' (zsh)"        $W "read 'GIT_DIR?Dir: ' <<< /x/.git; git add x"
assert_allow "496.I: for a b in x y"                     $W 'for a b in x y; do echo $a; done; git status'
assert_allow "496.I: read 'ans?Continue? '"              $W "read 'ans?Continue? ' <<< y; git status"
# J: an abbreviated sudo value option takes its value.
assert_deny  "496.J: sudo --us root git push"            $W 'sudo --us root git push'
# M: the other read-like builtins and print -v.
assert_deny_msg "496.M: readarray GIT_X"                 $W 'readarray GIT_X < f' "GIT_X"
assert_deny_msg "496.M: getopts ab GIT_DIR"              $W 'getopts ab GIT_DIR' "GIT_DIR"
assert_deny_msg "496.M: vared GIT_DIR (zsh)"             $W 'vared GIT_DIR' "GIT_DIR"
assert_deny_msg "496.M: print -v GIT_DIR (zsh)"          $W 'print -v GIT_DIR /x/.git; git add x' "GIT_DIR"
assert_deny_msg "496.M: print -rv GIT_DIR (bundled)"     $W 'print -rv GIT_DIR /x/.git; git add x' "GIT_DIR"
assert_allow "496.M: printf -v of another name"          $W 'printf -v OUT %s x; printf "%s\n" "-$v"; git status'
# Round 3 extras: builtins that make a name or a trap run a command.
assert_deny  "496.R3: alias g='git push'"                $W $'alias g=\'git push\'\ng'
assert_deny  "496.R3: hash -p /usr/bin/git g"            $W 'hash -p /usr/bin/git g; g push'
assert_deny  "496.R3: hash g=/usr/bin/git (zsh)"         $W 'hash g=/usr/bin/git; g push'
assert_deny  "496.R3: trap 'git push' EXIT"              $W "trap 'git push' EXIT"
assert_deny  "496.R3: emulate sh -c 'git push'"          $W "emulate sh -c 'git push'"
assert_deny  "496.R3: mapfile -C 'git push' callback"    $W "mapfile -C 'git push' -c 1 arr < f"
assert_allow "496.R3: trap cleanup / hash -r / alias list" $W "trap 'rm -rf \"\$TMP\"' EXIT; hash -r; alias; git status"

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
