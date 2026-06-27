#!/bin/bash
# Auto-push any projects to GitHub under the authenticated user's account.
set -uo pipefail

ROOTS=( "$HOME/projects" "$HOME/dev" "$HOME" )
SCAN_DEPTH=3
AUTO_CREATE_REPO=1
PUSH_TIMEOUT=300
MAX_REPOS=20

cd "$HOME"

GH_USER="$(gh api user --jq .login 2>/dev/null || true)"
if [[ -z "${GH_USER}" ]]; then
  echo "ERROR: gh is not authenticated." >&2
  exit 1
fi

count=0
found=()
for root in "${ROOTS[@]}"; do
  [[ -d "$root" ]] || continue
  while IFS= read -r -d '' d; do
    found+=("$d")
    count=$(( count + 1 ))
    [[ $count -ge $MAX_REPOS ]] && break
  done < <(find "$root" -maxdepth "$SCAN_DEPTH" -type d -name .git -print0 2>/dev/null)
  [[ $count -ge $MAX_REPOS ]] && break
done

echo "Found ${#found[@]} git repo(s)"

for d in "${found[@]}"; do
  repo_dir="$(dirname "$d")"
  repo_name="$(basename "$repo_dir")"

  pushd "$repo_dir" >/dev/null 2>&1 || { popd >/dev/null 2>&1 || true; continue; }

  remote_url="$(git remote get-url origin 2>/dev/null || true)"

  if [[ -z "$remote_url" ]]; then
    if [[ "$AUTO_CREATE_REPO" -eq 1 ]]; then
      echo "[$repo_name] no remote -> creating github.com/$GH_USER/$repo_name"
      if gh repo view "$GH_USER/$repo_name" >/dev/null 2>&1; then
        echo "  repo already exists on GitHub"
      else
        gh repo create "$GH_USER/$repo_name" --public --confirm --source . --remote origin --push 2>&1 || echo "  create+push failed for $repo_name"
        popd >/dev/null 2>&1 || true
        continue
      fi
    else
      echo "[$repo_name] no remote; skipping (AUTO_CREATE_REPO=0)"
      popd >/dev/null 2>&1 || true
      continue
    fi
  else
    echo "[$repo_name] remote present"
  fi

  current_branch="$(git symbolic-ref --short HEAD 2>/dev/null || true)"
  if [[ -n "$current_branch" ]]; then
    echo "  pushing $current_branch ..."
    timeout "$PUSH_TIMEOUT" git push -u origin "$current_branch" 2>&1 || echo "  push skipped/failed for $repo_name"
  else
    echo "  no current branch; skipping push"
  fi

  popd >/dev/null 2>&1 || true
done

echo "Done."
