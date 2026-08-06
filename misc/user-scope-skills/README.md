# User-Scope Skills Staging

These SKILL.md files are user-scope, not project-scope. They apply across all projects, not just Forge-OH.

**Install to Colossus:**

```bash
cd ~/dev/forge-oh
git pull
mkdir -p ~/.agents/skills
for d in misc/user-scope-skills/*/; do
    name=$(basename "$d")
    [ "$name" = "README.md" ] && continue
    rm -rf ~/.agents/skills/"$name"
    cp -r "$d" ~/.agents/skills/"$name"
done
ls ~/.agents/skills/
```

**Do NOT** put user-scope skills into `.agents/skills/` — that's for project-scope only. The OpenHands SDK loads `.agents/skills/` as project-scope skills, which means they'd only fire in Forge-OH sessions, defeating the purpose.

**Files here:** 15 SKILL.md directories covering general engineering discipline (Python testing, Git workflow, benchmarking, LLM serving pitfalls, deep research, planning, skill-authoring itself, etc.). See each SKILL.md's frontmatter for triggers and scope.

Contents will drift over time — the source of truth is `~/.agents/skills/` on the workstation. This staging area exists so a `git pull` can deliver updates.
