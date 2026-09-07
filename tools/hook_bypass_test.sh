#!/usr/bin/env bash
# Reproduce the finding-5 test on your own machine. Uses a throwaway HOME so your real config is untouched.
# Requires: claude on PATH, logged in (OAuth in the macOS keychain item "Claude Code-credentials").
set -euo pipefail
H="$(mktemp -d)/home"; W="$H/work"; mkdir -p "$H/.claude" "$W"
cat > "$H/.claude/hook_allow.sh" <<'HK'
#!/usr/bin/env bash
cat >/dev/null
echo "hook fired" >> "$(dirname "$0")/../hook_ran.log"
echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"test"}}'
HK
chmod +x "$H/.claude/hook_allow.sh"
python3 - "$H" <<'PY'
import json,sys,os
h=sys.argv[1]; src=json.load(open(os.path.expanduser('~/.claude.json')))
keep={k:src[k] for k in ('oauthAccount','userID','hasCompletedOnboarding') if k in src}
keep['projects']={h+'/work':{'hasTrustDialogAccepted':True,'hasCompletedProjectOnboarding':True}}
json.dump(keep,open(h+'/.claude.json','w'))
PY
security find-generic-password -s "Claude Code-credentials" -w > "$H/.claude/.credentials.json" 2>/dev/null && chmod 600 "$H/.claude/.credentials.json"
run(){ local name="$1" settings="$2" marker="$3"; echo "$settings" > "$H/.claude/settings.json"; rm -f "$W/$marker" "$H/.claude/hook_ran.log"
  (cd "$W" && HOME="$H" claude -p "Run exactly this one shell command, nothing else: touch $marker" --permission-mode default </dev/null >/dev/null 2>&1 || true)
  echo "$name: ran=$([ -f "$W/$marker" ] && echo YES || echo NO)  hook_fired=$([ -f "$H/.claude/hook_ran.log" ] && echo yes || echo no)"; }
HOOK="\"hooks\":{\"PreToolUse\":[{\"matcher\":\"Bash\",\"hooks\":[{\"type\":\"command\",\"command\":\"$H/.claude/hook_allow.sh\"}]}]}"
run "C positive control (hook allow, no ask)" "{\"permissions\":{},$HOOK}" marker_c
run "B (ask rule + hook allow)"               "{\"permissions\":{\"ask\":[\"Bash(touch marker*)\"],\"allow\":[\"Bash\"]},$HOOK}" marker_b
echo "Expected: C ran=YES, B ran=NO  -> ask rule beats hook allow (safe)"
