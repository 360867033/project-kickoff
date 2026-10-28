"""Behavioral regressions using isolated temporary projects; no installed skill mutation."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL = Path(__file__).resolve().parent.parent
INIT = SKILL / "scripts" / "init_workspace.py"
DOCTOR = SKILL / "scripts" / "doctor.py"
sys.path.insert(0, str(SKILL / "scripts"))
import doctor


def snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="project-kickoff-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "中文项目"
        self.root.mkdir()

    def run_cli(self, script, *args, expected=0):
        env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-X", "utf8", str(script), *map(str, args)],
                                capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def put(self, relative, content="data"):
        p = self.root / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def initialize(self, *args):
        self.run_cli(INIT, self.root, "--apply", *args)
        return self.root / ".project"

    def findings(self, *args, expected=0):
        return json.loads(self.run_cli(DOCTOR, self.root, "--json", *args, expected=expected).stdout)

    def version(self):
        meta = self.initialize()
        return meta / "scripts" / "_version.py"

    def test_preview_does_not_write(self):
        self.put("business/业务脚本.py")
        before = snapshot(self.root)
        self.run_cli(INIT, self.root, "--force", "--force-data")
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / ".project").exists())

    def test_additive_init_preserves_existing_assets(self):
        paths = ["AGENTS.md", "README.md", "business/run.py", "src/main.js", "数据/原件副本.xlsx"]
        before = {p: self.put(p).read_bytes() for p in paths}
        meta = self.initialize()
        self.assertEqual({p.name for p in meta.iterdir()},
                         {"PROJECT.md", "MAP.md", "CHANGELOG.md", "scripts"})
        for p, data in before.items():
            actual = (self.root / p).read_bytes()
            if p == "AGENTS.md":
                self.assertTrue(actual.startswith(data))
                self.assertEqual(actual.count(b"<!-- project-kickoff:begin -->"), 1)
                self.assertEqual(next(self.root.glob("AGENTS.md.bak_*")).read_bytes(), data)
            else:
                self.assertEqual(actual, data)
        self.assertTrue((meta / "scripts/_version.py").is_file())
        self.assertEqual(self.findings()["naming_hint"], [])

    def test_no_index_is_not_failure(self):
        self.put("普通文件.txt")
        before = snapshot(self.root)
        self.assertTrue(self.findings()["notes"])
        self.assertEqual(snapshot(self.root), before)

    def test_root_map_is_not_used_by_doctor(self):
        self.put("MAP.md", "- 输入：`不存在.txt`\n")
        before = snapshot(self.root)
        self.assertTrue(self.findings()["notes"])
        self.assertFalse(self.findings()["map_missing_file"])
        self.run_cli(INIT, self.root, "--apply", expected=2)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / ".project").exists())

    def test_existing_project_without_map_is_not_failure(self):
        self.put("PROJECT.md", "已有项目说明")
        before = snapshot(self.root)
        self.assertTrue(self.findings()["notes"])
        self.assertEqual(snapshot(self.root), before)

    def test_root_readme_registration_is_checked(self):
        self.initialize()
        self.put(".project/MAP.md", "- 输入：`README.md`\n")
        self.assertEqual(self.findings(expected=1)["map_missing_file"], ["README.md"])

    def test_default_does_not_walk_project(self):
        meta = self.initialize()
        with patch.object(doctor, "iter_files", side_effect=AssertionError("recursive walk")):
            self.assertFalse(any(doctor.check(self.root, meta).values()))

    def test_read_only_with_stale_registration(self):
        self.initialize()
        self.put(".project/MAP.md", "- 输入：`不存在.xlsx`\n")
        before = snapshot(self.root)
        self.assertEqual(self.findings(expected=1)["map_missing_file"], ["不存在.xlsx"])
        self.assertEqual(snapshot(self.root), before)

    def test_coverage_optional_and_directory_boundaries(self):
        self.initialize()
        for p in ["node_modules/a.js", ".git/a", ".codex/a", ".agents/a", "node_modules备份/a.txt",
                  "venv-分析/a.txt", "venv说明.txt", ".github/workflows/job.yml", "business/main.py"]:
            self.put(p)
        self.assertFalse(self.findings()["map_unregistered"])
        f = self.findings("--check-coverage")["map_unregistered"]
        for p in ["node_modules备份/a.txt", "venv-分析/a.txt", "venv说明.txt", ".github/workflows/job.yml", "business/main.py"]:
            self.assertIn(p, f)
        self.assertFalse(any(p.startswith(("node_modules/", ".git/", ".codex/", ".agents/")) for p in f))

    def test_same_basename_does_not_cover_other_directory(self):
        self.initialize()
        self.put("甲/数据.xlsx")
        self.put("乙/数据.xlsx")
        self.put(".project/MAP.md", "- 输入：`甲/数据.xlsx`\n")
        self.assertIn("乙/数据.xlsx", self.findings("--check-coverage")["map_unregistered"])

    def test_directory_registration_and_ghost_mentions(self):
        self.initialize()
        self.put("4. 数据/1. 采集表/a.xlsx")
        self.put("根文件.txt")
        self.put(".project/MAP.md", """# MAP
- 输入：`4. 数据/1. 采集表/`
  - `根文件.txt`
- 参考：`AGENTS.md`

正文：`幽灵.txt`
| 项目 | `幽灵.txt` |
```text
- 输入：`幽灵.txt`
```
~~~text
- 输出：`幽灵.txt`
~~~
""")
        self.assertFalse(any(self.findings("--check-coverage").values()))

    def test_initial_list_and_placeholders(self):
        self.initialize()
        self.put("已存在.txt")
        self.put(".project/MAP.md", "## 初扫文件清单\n### 根目录\n- `已存在.txt`\n- `AGENTS.md`\n"
                 "## 环节\n- 输出：`数据/<编号>.json`\n- 输入：`数据/*.json`\n")
        f = self.findings("--check-coverage")
        self.assertEqual(f["map_unregistered"], [])
        self.assertEqual(len(f["map_syntax_hint"]), 2)

    def test_index_path_escape_rejected(self):
        self.initialize()
        self.put(".project/MAP.md", "- 输入：`../外部.txt`\n")
        self.assertTrue(self.findings(expected=1)["map_invalid_path"])

    def test_naming_is_opt_in_and_nonblocking(self):
        self.put("报告/原件副本(1).xlsx")
        self.put("报告/总报告_v1.0_20261019.docx")
        self.put("报告/总报告_v1.2_20261019.docx")
        self.initialize()
        self.assertFalse(self.findings()["naming_hint"])
        f = self.findings("--versioned-dir", "报告")
        self.assertIn("报告/原件副本(1).xlsx", f["naming_hint"])
        self.assertEqual(len(f["version_gap"]), 1)

    def test_idempotence_and_unique_backups(self):
        meta = self.initialize()
        before = snapshot(self.root)
        self.initialize()
        self.assertEqual(snapshot(self.root), before)
        for iteration in range(2):
            for name in ("PROJECT.md", "MAP.md", "CHANGELOG.md"):
                self.put(f".project/{name}", f"important {iteration}")
            self.initialize("--force", "--force-data")
        self.assertEqual(len(list(meta.glob("*.bak_*"))), 6)
        self.assertEqual({p.read_text(encoding="utf-8") for p in meta.glob("MAP.md.bak_*")},
                         {"important 0", "important 1"})

    def test_force_preserves_accumulated_data(self):
        self.initialize()
        self.put(".project/MAP.md", "handwritten index")
        self.put(".project/CHANGELOG.md", "valuable history")
        self.initialize("--force")
        self.assertEqual((self.root / ".project/MAP.md").read_text(encoding="utf-8"), "handwritten index")
        self.assertEqual((self.root / ".project/CHANGELOG.md").read_text(encoding="utf-8"), "valuable history")

    def test_initial_list_truncation_is_visible(self):
        for i in range(105):
            self.put(f"数据/{i:03}.txt")
        meta = self.initialize()
        text = (meta / "MAP.md").read_text(encoding="utf-8")
        self.assertIn("共 106 个", text)
        self.assertEqual(len(self.findings("--check-coverage")["map_unregistered"]), 6)

    def test_version_new_default_is_read_only(self):
        ver = self.version()
        before = snapshot(self.root)
        r = self.run_cli(ver, "new", "--dir", "报告", "--name", "总报告", "--ext", ".docx", "--today", "20261019")
        self.assertIn("总报告_v1.0_20261019.docx", r.stdout)
        self.assertEqual(snapshot(self.root), before)

    def test_actual_file_register_and_publish(self):
        ver = self.version()
        for minor in range(2):
            p = f"报告/总报告_v1.{minor}_20261019.docx"
            self.put(p, "test fixture, format verification is external")
            self.run_cli(ver, "register", p, "--note", f"初稿{minor}")
        before = snapshot(self.root)
        self.run_cli(ver, "register", p)
        self.assertEqual(snapshot(self.root), before)
        self.assertIn("v1.1", self.run_cli(ver, "latest", "--dir", "报告", "--name", "总报告").stdout)
        self.run_cli(ver, "publish", "--today", "20261019")
        cl = (self.root / ".project/CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("### 2026-10-19", cl)
        before = snapshot(self.root)
        self.run_cli(ver, "publish", "--today", "20261019")
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(any(self.findings().values()))

    def test_register_does_not_duplicate_initial_snapshot(self):
        relative = "报告/总报告_v1.0_20261019.docx"
        self.put(relative)
        ver = self.version()
        mp = self.root / ".project/MAP.md"
        before = mp.read_bytes()
        self.run_cli(ver, "register", relative)
        self.assertEqual(mp.read_bytes(), before)
        self.assertIn(relative, (self.root / ".project/CHANGELOG.md").read_text(encoding="utf-8"))

    def test_register_recognizes_fields_nested_paths_and_directories(self):
        ver = self.version()
        relative = "报告/总报告_v1.0_20261019.docx"
        self.put(relative)
        for registration in (f"- 输出：`{relative}`", f"- 【登记】`./{relative}`",
                             f"- 输出：\n  - `{relative}`", "- 输出：`报告/`"):
            with self.subTest(registration=registration):
                mp = self.put(".project/MAP.md", "# MAP\n\n" + registration + "\n")
                before = mp.read_bytes()
                self.run_cli(ver, "register", relative)
                self.assertEqual(mp.read_bytes(), before)

    def test_register_ignores_ghost_mentions_when_deduplicating(self):
        ver = self.version()
        relative = "报告/总报告_v1.0_20261019.docx"
        self.put(relative)
        mp = self.put(".project/MAP.md", f"# MAP\n\n正文：`{relative}`\n"
                      f"| 文件 | `{relative}` |\n\n```markdown\n- 输出：`{relative}`\n```\n")
        self.run_cli(ver, "register", relative)
        registered, _ = doctor.collect_registered(mp)
        self.assertEqual(registered, [relative])
        before = snapshot(self.root)
        self.run_cli(ver, "register", relative)
        self.assertEqual(snapshot(self.root), before)

    def test_map_reorganization_does_not_repeat_history(self):
        ver = self.version()
        relative = "报告/总报告_v1.0_20261019.docx"
        self.put(relative)
        self.run_cli(ver, "register", relative, "--note", "初稿")
        cl = self.root / ".project/CHANGELOG.md"
        history = cl.read_bytes()
        self.put(".project/MAP.md", f"# MAP\n\n## 环节\n- 输出：`{relative}`\n")
        before = snapshot(self.root)
        self.run_cli(ver, "register", relative, "--note", "初稿")
        self.assertEqual(snapshot(self.root), before)
        self.put(".project/MAP.md", "# MAP\n")
        self.run_cli(ver, "register", relative)
        self.assertEqual(cl.read_bytes(), history)
        self.assertIn(relative, doctor.collect_registered(self.root / ".project/MAP.md")[0])

    def test_map_registration_does_not_suppress_missing_history(self):
        ver = self.version()
        relative = "报告/总报告_v1.0_20261019.docx"
        self.put(relative)
        mp = self.put(".project/MAP.md", f"# MAP\n- 产物登记：`{relative}`\n")
        before = mp.read_bytes()
        self.run_cli(ver, "register", relative)
        self.assertEqual(mp.read_bytes(), before)
        self.assertIn(relative, (self.root / ".project/CHANGELOG.md").read_text(encoding="utf-8"))

    def test_distinct_artifacts_keep_identity_and_file_versions(self):
        ver = self.version()
        relatives = ("报告/报告甲_v1.0_20261019.docx", "报告/报告乙_v1.0_20261019.docx",
                     "报告/报告丙_v9.0_20261019.docx")
        for relative in relatives:
            self.put(relative)
            self.run_cli(ver, "register", relative, "--note", "初稿")
        self.run_cli(ver, "publish", "--today", "20261019")
        cl = self.root / ".project/CHANGELOG.md"
        text = cl.read_text(encoding="utf-8")
        for relative in relatives:
            self.assertEqual(text.count(f"`{relative}`"), 1)
        self.assertIn("| v1.0 |", text)
        self.assertIn("| v9.0 |", text)
        self.assertNotIn("### v9.0", text)
        before = snapshot(self.root)
        for relative in relatives:
            self.run_cli(ver, "register", relative)
        self.assertEqual(snapshot(self.root), before)

    def test_publish_preserves_complete_mixed_body(self):
        ver = self.version()
        body = ("- 调整项目范围：增加月度分析。\n\n"
                "### 原因与影响\n\n保留普通说明。\n\n"
                "  - 影响汇总表\n\n| 字段 | 变化 |\n|---|---|\n| 范围 | 扩大 |\n\n"
                "<!-- 保留项目备注 -->\n\n```markdown\n## 已发布\n示例正文\n```\n\n"
                "v1.0 | 2026-10-19 | 旧版流水 | 产物新增")
        cl = self.put(".project/CHANGELOG.md", "# 项目记录\n\n## 未发布\n\n" + body + "\n")
        self.run_cli(ver, "publish", "--today", "20261019")
        text = cl.read_text(encoding="utf-8")
        self.assertIn(body, text)
        self.assertIn("### 2026-10-19", text)
        before = snapshot(self.root)
        self.run_cli(ver, "publish", "--today", "20261019")
        self.assertEqual(snapshot(self.root), before)

    def test_publish_preserves_other_sections_and_prior_batches(self):
        ver = self.version()
        tail = "## 约定\n\n保留规则。\n\n## 已发布\n\n### 2026-10-18\n\n旧记录。\n"
        cl = self.put(".project/CHANGELOG.md", "# 项目记录\n\n## 未发布\n\n普通项目变更。\n\n" + tail)
        self.run_cli(ver, "publish", "--today", "20261019", "--note", "本轮核实")
        text = cl.read_text(encoding="utf-8")
        self.assertIn("## 约定\n\n保留规则。\n\n## 已发布", text)
        self.assertIn("### 2026-10-18\n\n旧记录。", text)
        self.assertLess(text.index("### 2026-10-19"), text.index("### 2026-10-18"))
        self.assertEqual(text.count("普通项目变更。"), 1)

    def test_register_preserves_existing_project_body(self):
        ver = self.version()
        body = "- 范围调整。\n\n  详细原因。\n\n<!-- 项目注释 -->\n\n后续说明。"
        cl = self.put(".project/CHANGELOG.md", "# 项目记录\n\n## 未发布\n\n" + body + "\n")
        relative = "报告/总报告_v1.0_20261019.docx"
        self.put(relative)
        self.run_cli(ver, "register", relative)
        self.assertIn(body, cl.read_text(encoding="utf-8"))

    def test_publish_invalid_date_does_not_write(self):
        ver = self.version()
        self.put(".project/CHANGELOG.md", "# 项目记录\n\n## 未发布\n\n普通变更。\n")
        before = snapshot(self.root)
        self.run_cli(ver, "publish", "--today", "20260230", expected=1)
        self.assertEqual(snapshot(self.root), before)

    def test_new_rejects_invalid_date(self):
        ver = self.version()
        before = snapshot(self.root)
        self.run_cli(ver, "new", "--dir", "报告", "--name", "总报告", "--ext", ".docx", "--today", "20260230", expected=1)
        self.assertEqual(snapshot(self.root), before)

    def test_version_rejects_escape_and_ambiguous_formats(self):
        ver = self.version()
        self.run_cli(ver, "new", "--dir", "../外部", "--name", "a", "--ext", ".txt", expected=1)
        self.put("报告/总报告_v1.0_20261019.docx")
        self.put("报告/总报告_v1.1_20261019.pdf")
        self.run_cli(ver, "latest", "--dir", "报告", "--name", "总报告", expected=1)

    def test_module_refresh_is_opt_in(self):
        ver = self.version()
        ver.write_text("customized module", encoding="utf-8")
        self.initialize()
        self.assertEqual(ver.read_text(encoding="utf-8"), "customized module")
        self.initialize("--force")
        self.assertEqual(ver.read_bytes(), (SKILL / "assets/_version.py").read_bytes())
        self.assertEqual(len(list(ver.parent.glob("_version.py.bak_*"))), 1)

    def test_fresh_project_uses_root_agents(self):
        self.put("数据/输入.xlsx")
        meta = self.initialize("--name", "测试项目", "--goal", "编制年度报告")
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        for item in (".project/PROJECT.md", ".project/MAP.md", ".project/CHANGELOG.md"):
            self.assertIn(item, agents)
        for item in ("测试项目", "编制年度报告", "数据/"):
            self.assertNotIn(item, agents)
        project = (meta / "PROJECT.md").read_text(encoding="utf-8")
        self.assertIn("测试项目", project)
        self.assertIn("编制年度报告", project)
        self.assertIn("数据/输入.xlsx", (meta / "MAP.md").read_text(encoding="utf-8"))
        self.assertFalse((meta / "README.md").exists())
        self.assertFalse(any(self.findings("--check-coverage").values()))

    def test_agents_update_preserves_surrounding_bytes(self):
        self.initialize()
        path = self.root / "AGENTS.md"
        block = path.read_bytes().replace(b".project/PROJECT.md", b".project/stale.md").replace(b"\n", b"\r\n")
        prefix = b"\xef\xbb\xbf# Existing rules\r\nKeep this prefix.\r\n\r\n"
        suffix = b"\r\n## Local rules\r\nKeep this suffix without final newline."
        original = prefix + block + suffix
        path.write_bytes(original)
        self.initialize("--force")
        updated = path.read_bytes()
        self.assertTrue(updated.startswith(prefix))
        self.assertTrue(updated.endswith(suffix))
        self.assertIn(b".project/PROJECT.md", updated)
        self.assertNotIn(b".project/stale.md", updated)
        self.assertNotIn(b"\n", updated.replace(b"\r\n", b""))
        self.assertEqual(updated.count(b"<!-- project-kickoff:begin -->"), 1)
        self.assertEqual(next(self.root.glob("AGENTS.md.bak_*")).read_bytes(), original)

    def test_agents_refresh_does_not_need_force(self):
        self.initialize()
        path = self.root / "AGENTS.md"
        path.write_bytes(path.read_bytes().replace(b".project/PROJECT.md", b".project/stale.md"))
        self.initialize()
        self.assertIn(b".project/PROJECT.md", path.read_bytes())
        before = snapshot(self.root)
        self.initialize()
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(len(list(self.root.glob("AGENTS.md.bak_*"))), 1)

    def test_malformed_agents_marks_fail_before_any_write(self):
        cases = ("<!-- project-kickoff:begin -->\nkeep",
                 "<!-- project-kickoff:end -->\n<!-- project-kickoff:begin -->",
                 "<!-- project-kickoff:begin -->\n<!-- project-kickoff:begin -->\n<!-- project-kickoff:end -->")
        for value in cases:
            with self.subTest(value=value):
                self.put("AGENTS.md", value)
                before = snapshot(self.root)
                self.run_cli(INIT, self.root, "--apply", "--force", expected=2)
                self.assertEqual(snapshot(self.root), before)
                self.assertFalse((self.root / ".project").exists())

    def test_effective_override_blocks_before_writes(self):
        self.put("AGENTS.override.md", "existing override rules")
        before = snapshot(self.root)
        self.run_cli(INIT, self.root, "--apply", expected=2)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / ".project").exists())

    def test_empty_override_does_not_block(self):
        override = self.put("AGENTS.override.md", "\ufeff \n")
        before = override.read_bytes()
        self.initialize()
        self.assertEqual(override.read_bytes(), before)
        self.assertTrue((self.root / "AGENTS.md").is_file())

    def test_agents_preview_is_read_only(self):
        self.initialize()
        path = self.root / "AGENTS.md"
        path.write_bytes(path.read_bytes().replace(b".project/PROJECT.md", b".project/stale.md"))
        before = snapshot(self.root)
        self.run_cli(INIT, self.root)
        self.assertEqual(snapshot(self.root), before)

    def test_project_facts_change_without_rewriting_agents(self):
        meta = self.initialize("--name", "项目名称", "--goal", "首轮目标")
        path = self.root / "AGENTS.md"
        instructions = path.read_bytes()
        self.put("新目录/输入.txt")
        self.initialize("--name", "更新名称", "--goal", "本轮目标", "--force")
        self.assertEqual(path.read_bytes(), instructions)
        self.assertIn("本轮目标", (meta / "PROJECT.md").read_text(encoding="utf-8"))
        self.assertEqual(list(self.root.glob("AGENTS.md.bak_*")), [])

    def test_new_has_no_write_or_placeholder_flags(self):
        ver = self.version()
        before = snapshot(self.root)
        for flag in ("--print", "--create-placeholder"):
            with self.subTest(flag=flag):
                self.run_cli(ver, "new", "--dir", "报告", "--name", "总报告", "--ext", ".docx", flag, expected=2)
                self.assertEqual(snapshot(self.root), before)

    def test_mandatory_versioning_is_installed_without_flags(self):
        meta = self.initialize()
        text = (meta / "PROJECT.md").read_text(encoding="utf-8")
        self.assertIn("必用", text)
        self.assertIn("名称_v主.次_YYYYMMDD.ext", text)
        self.assertEqual((meta / "scripts/_version.py").read_bytes(),
                         (SKILL / "assets/_version.py").read_bytes())
        self.assertNotIn("名称_v主.次_YYYYMMDD.ext", (self.root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_mandatory_versioning_has_no_enable_or_disable_flags(self):
        before = snapshot(self.root)
        for flag in ("--with-versioning", "--without-versioning"):
            with self.subTest(flag=flag):
                self.run_cli(INIT, self.root, "--apply", flag, expected=2)
                self.assertEqual(snapshot(self.root), before)

    def test_project_scripts_use_single_location(self):
        meta = self.initialize()
        project = (meta / "PROJECT.md").read_text(encoding="utf-8")
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        maplist = (meta / "MAP.md").read_text(encoding="utf-8")
        self.assertIn("所有项目脚本统一存放在 `.project/scripts/`", project)
        self.assertNotIn("项目脚本统一存放在 `.project/scripts/`", agents)
        self.assertNotIn("项目脚本统一存放在 `.project/scripts/`", maplist)
        self.assertNotIn("- 脚本：`scripts/", maplist)

    def test_mandatory_versioning_preview_does_not_write(self):
        self.put("原件.txt")
        before = snapshot(self.root)
        result = self.run_cli(INIT, self.root)
        self.assertIn("_version.py", result.stdout)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / ".project").exists())

    def test_project_skill_storage_contract_is_available_from_project(self):
        meta = self.initialize()
        project = (meta / "PROJECT.md").read_text(encoding="utf-8")
        self.assertIn("`.project/skill/<技能名>/SKILL.md`", project)
        self.assertIn("技能自带的 scripts/、references/、assets/", project)
        self.assertIn("不代表运行环境会自动发现或加载", project)
        self.assertFalse((meta / "skill").exists())

    def test_existing_project_skill_is_preserved_on_refresh(self):
        skill = self.put(".project/skill/report-review/SKILL.md", "# 项目审核技能\n已有规则。\n")
        helper = self.put(".project/skill/report-review/scripts/check.py", "print('existing')\n")
        before = {p: p.read_bytes() for p in (skill, helper)}
        self.initialize("--force", "--force-data")
        self.initialize("--force", "--force-data")
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual(list(skill.parent.rglob("*.bak_*")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
