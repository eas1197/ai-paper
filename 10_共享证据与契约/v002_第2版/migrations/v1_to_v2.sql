-- 新版允许研究启动时议题为空；旧行及其他表不改变。
-- 独立连接中执行，执行前备份；本项目本轮仅在测试库验证，不迁移正式库。
PRAGMA foreign_keys=OFF;
BEGIN IMMEDIATE;
CREATE TABLE research_runs_v2(
 run_id TEXT PRIMARY KEY, theme TEXT NOT NULL, issue TEXT,
 question TEXT, config_sha256 TEXT NOT NULL, requirements_sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL, status TEXT NOT NULL
);
INSERT INTO research_runs_v2 SELECT run_id,theme,issue,question,config_sha256,requirements_sha256,created_at,status FROM research_runs;
DROP TABLE research_runs;
ALTER TABLE research_runs_v2 RENAME TO research_runs;
COMMIT;
PRAGMA foreign_keys=ON;
PRAGMA foreign_key_check;
