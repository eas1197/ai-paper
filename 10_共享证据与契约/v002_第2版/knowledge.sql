-- 第1版结构定义。空库初始化；不包含伪造的正式文献或结果。
PRAGMA foreign_keys = ON;
CREATE TABLE schema_info(version INTEGER PRIMARY KEY, created_on TEXT NOT NULL);
INSERT INTO schema_info VALUES(1,'2026-11-14');
CREATE TABLE sources(
 source_id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
 url_or_path TEXT NOT NULL, retrieved_at TEXT NOT NULL,
 sha256 TEXT, access_basis TEXT NOT NULL, share_scope TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('unverified','verified','rejected'))
);
CREATE TABLE documents(
 document_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources,
 local_path TEXT, sha256 TEXT, document_type TEXT NOT NULL,
 fulltext_status TEXT NOT NULL, identity_verified INTEGER NOT NULL DEFAULT 0
 CHECK(identity_verified IN (0,1))
);
CREATE TABLE journals(
 journal_id TEXT PRIMARY KEY, name TEXT NOT NULL, issn TEXT, cn TEXT,
 profile_json TEXT NOT NULL, quota_group TEXT CHECK(quota_group IN ('CSSCI','PKU')),
 as_of TEXT NOT NULL, verification_status TEXT NOT NULL,
 unknown_reason TEXT
);
CREATE TABLE journal_evidence(
 journal_id TEXT NOT NULL REFERENCES journals,
 field_name TEXT NOT NULL, document_id TEXT NOT NULL REFERENCES documents,
 locator TEXT NOT NULL, verified_at TEXT NOT NULL,
 PRIMARY KEY(journal_id,field_name,document_id,locator)
);
CREATE TABLE journal_metrics(
 metric_id TEXT PRIMARY KEY, journal_id TEXT NOT NULL REFERENCES journals,
 metric_name TEXT NOT NULL, metric_year INTEGER, value REAL, provider TEXT,
 source_id TEXT REFERENCES sources, unknown_reason TEXT
);
CREATE TABLE journal_fees(
 fee_id TEXT PRIMARY KEY, journal_id TEXT NOT NULL REFERENCES journals,
 fee_type TEXT NOT NULL, amount_min REAL, amount_max REAL,
 currency TEXT, unit TEXT, waiver TEXT, source_id TEXT REFERENCES sources,
 verified_at TEXT, unknown_reason TEXT
);
CREATE TABLE papers(
 paper_id TEXT PRIMARY KEY, title TEXT NOT NULL, authors_json TEXT NOT NULL,
 year INTEGER, journal_name TEXT, journal_id TEXT REFERENCES journals,
 doi TEXT UNIQUE, source_record_id TEXT, abstract TEXT,
 metadata_source_id TEXT NOT NULL REFERENCES sources,
 abstract_read_at TEXT, fulltext_document_id TEXT REFERENCES documents,
 fulltext_read_at TEXT, verification_status TEXT NOT NULL
);
CREATE TABLE corpus_membership(
 corpus_id TEXT NOT NULL, paper_id TEXT NOT NULL REFERENCES papers,
 purpose TEXT NOT NULL, selection_reason TEXT NOT NULL,
 read_requirement TEXT NOT NULL, PRIMARY KEY(corpus_id,paper_id)
);
CREATE TABLE evidence(
 evidence_id TEXT PRIMARY KEY, paper_id TEXT REFERENCES papers,
 document_id TEXT NOT NULL REFERENCES documents, locator TEXT NOT NULL,
 short_excerpt TEXT, paraphrase TEXT NOT NULL,
 evidence_class TEXT NOT NULL CHECK(evidence_class IN ('direct','synthesis','inference')),
 stance TEXT NOT NULL CHECK(stance IN ('support','contradict','qualify','context')),
 extraction_method TEXT NOT NULL, review_status TEXT NOT NULL,
 source_sha256 TEXT NOT NULL
);
CREATE TABLE structure_moves(
 move_id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers,
 section_title TEXT NOT NULL, section_order INTEGER NOT NULL,
 paragraph_no INTEGER, sentence_no INTEGER, move_code TEXT NOT NULL,
 sequence_description TEXT NOT NULL, word_count INTEGER,
 evidence_id TEXT NOT NULL REFERENCES evidence
);
CREATE TABLE language_rules(
 rule_id TEXT PRIMARY KEY, rhetorical_move TEXT NOT NULL,
 rule_text TEXT NOT NULL, original_example TEXT NOT NULL,
 counterexample TEXT, preconditions TEXT NOT NULL, review_status TEXT NOT NULL
);
CREATE TABLE language_evidence(
 rule_id TEXT NOT NULL REFERENCES language_rules,
 evidence_id TEXT NOT NULL REFERENCES evidence, PRIMARY KEY(rule_id,evidence_id)
);
CREATE TABLE relations(
 relation_id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers,
 x_concept TEXT NOT NULL, y_concept TEXT NOT NULL,
 mediator TEXT, moderator TEXT, relation_type TEXT NOT NULL,
 direction TEXT NOT NULL, mechanism TEXT, unit TEXT NOT NULL,
 scope_json TEXT NOT NULL, claimed_strength TEXT NOT NULL,
 supported_strength TEXT NOT NULL, read_basis TEXT NOT NULL,
 review_status TEXT NOT NULL
);
CREATE TABLE relation_evidence(
 relation_id TEXT NOT NULL REFERENCES relations,
 evidence_id TEXT NOT NULL REFERENCES evidence, PRIMARY KEY(relation_id,evidence_id)
);
CREATE TABLE research_runs(
 run_id TEXT PRIMARY KEY, theme TEXT NOT NULL, issue TEXT,
 question TEXT, config_sha256 TEXT NOT NULL, requirements_sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE hypotheses(
 hypothesis_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs,
 gap_type TEXT NOT NULL CHECK(gap_type IN ('reality_theory_tension','same_level_gap','scope_change','relation_revision')),
 question TEXT NOT NULL, specification_json TEXT NOT NULL,
 same_level_checks_json TEXT NOT NULL, falsification TEXT NOT NULL,
 causal_claim_level TEXT NOT NULL, review_status TEXT NOT NULL
);
CREATE TABLE hypothesis_evidence(
 hypothesis_id TEXT NOT NULL REFERENCES hypotheses,
 evidence_id TEXT NOT NULL REFERENCES evidence, role TEXT NOT NULL,
 PRIMARY KEY(hypothesis_id,evidence_id,role)
);
CREATE TABLE datasets(
 dataset_id TEXT PRIMARY KEY, name TEXT NOT NULL, wave TEXT NOT NULL,
 source_id TEXT NOT NULL REFERENCES sources, file_path TEXT NOT NULL,
 file_sha256 TEXT NOT NULL, questionnaire_document_id TEXT REFERENCES documents,
 raw_identity_status TEXT NOT NULL, access_conditions TEXT NOT NULL
);
CREATE TABLE variables(
 variable_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs,
 dataset_id TEXT NOT NULL REFERENCES datasets, source_variable TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('X','Y','M','Z','control','design','id')),
 concept TEXT NOT NULL, question_id TEXT, question_text TEXT,
 questionnaire_locator TEXT, variable_label TEXT, value_labels_json TEXT NOT NULL,
 special_missing_json TEXT NOT NULL, population TEXT NOT NULL,
 measurement_time TEXT NOT NULL, construction TEXT NOT NULL,
 rationale TEXT NOT NULL, review_status TEXT NOT NULL
);
CREATE TABLE variable_evidence(
 variable_id TEXT NOT NULL REFERENCES variables,
 evidence_id TEXT NOT NULL REFERENCES evidence, role TEXT NOT NULL,
 PRIMARY KEY(variable_id,evidence_id,role)
);
CREATE TABLE methods(
 method_id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
 assumptions_json TEXT NOT NULL, reporting_json TEXT NOT NULL,
 status TEXT NOT NULL
);
CREATE TABLE method_references(
 method_id TEXT NOT NULL REFERENCES methods, paper_id TEXT NOT NULL REFERENCES papers,
 reference_role TEXT NOT NULL, method_locator TEXT NOT NULL,
 table_locator TEXT, extracted_rules_json TEXT NOT NULL,
 review_status TEXT NOT NULL, PRIMARY KEY(method_id,paper_id)
);
CREATE TABLE models(
 model_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs,
 hypothesis_id TEXT REFERENCES hypotheses, method_id TEXT NOT NULL REFERENCES methods,
 sample_version TEXT NOT NULL, specification_json TEXT NOT NULL,
 code_path TEXT NOT NULL, code_sha256 TEXT NOT NULL,
 engine_environment_json TEXT NOT NULL, seed INTEGER,
 executed_at TEXT, diagnostic_status TEXT NOT NULL,
 result_status TEXT NOT NULL CHECK(result_status IN ('planned','failed','executed','verified'))
);
CREATE TABLE model_variables(
 model_id TEXT NOT NULL REFERENCES models, variable_id TEXT NOT NULL REFERENCES variables,
 PRIMARY KEY(model_id,variable_id)
);
CREATE TABLE results(
 result_id TEXT PRIMARY KEY, model_id TEXT NOT NULL REFERENCES models,
 outcome TEXT NOT NULL, term TEXT NOT NULL, estimate REAL NOT NULL,
 scale TEXT NOT NULL, std_error REAL, ci_low REAL, ci_high REAL,
 ci_level REAL, p_value REAL CHECK(p_value BETWEEN 0 AND 1),
 n_obs INTEGER NOT NULL CHECK(n_obs > 0), n_clusters INTEGER,
 output_document_id TEXT NOT NULL REFERENCES documents,
 verification_status TEXT NOT NULL
);
CREATE TABLE frozen_packs(
 pack_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs,
 manifest_path TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE drafts(
 draft_id TEXT PRIMARY KEY, pack_id TEXT NOT NULL REFERENCES frozen_packs,
 label TEXT NOT NULL CHECK(label IN ('A','B','C')),
 manuscript_family_id TEXT NOT NULL, file_path TEXT NOT NULL,
 file_sha256 TEXT NOT NULL, context_id TEXT NOT NULL,
 status TEXT NOT NULL, UNIQUE(pack_id,label)
);
CREATE TABLE claims(
 claim_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES drafts,
 sentence_locator TEXT NOT NULL, claim_text TEXT NOT NULL,
 claim_type TEXT NOT NULL, scope_limit TEXT NOT NULL, review_status TEXT NOT NULL
);
CREATE TABLE claim_evidence(
 claim_id TEXT NOT NULL REFERENCES claims, evidence_id TEXT NOT NULL REFERENCES evidence,
 PRIMARY KEY(claim_id,evidence_id)
);
CREATE TABLE claim_results(
 claim_id TEXT NOT NULL REFERENCES claims, result_id TEXT NOT NULL REFERENCES results,
 PRIMARY KEY(claim_id,result_id)
);
CREATE TABLE reviews(
 review_id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES drafts,
 rubric_version TEXT NOT NULL, hard_gates_passed INTEGER NOT NULL CHECK(hard_gates_passed IN (0,1)),
 score REAL CHECK(score BETWEEN 0 AND 100), findings_json TEXT NOT NULL,
 reviewed_at TEXT NOT NULL
);
CREATE TABLE submissions(
 submission_id TEXT PRIMARY KEY, manuscript_family_id TEXT NOT NULL,
 draft_id TEXT NOT NULL REFERENCES drafts, journal_id TEXT NOT NULL REFERENCES journals,
 adaptation_manifest_sha256 TEXT NOT NULL, status TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0,1)),
 submitted_at TEXT, release_evidence_id TEXT REFERENCES evidence,
 CHECK(active = CASE WHEN status IN ('submitted','under_review','accepted') THEN 1 ELSE 0 END)
);
CREATE UNIQUE INDEX one_active_submission_per_family
 ON submissions(manuscript_family_id) WHERE active=1;
CREATE TRIGGER submission_family_check BEFORE INSERT ON submissions
 WHEN NEW.manuscript_family_id != (SELECT manuscript_family_id FROM drafts WHERE draft_id=NEW.draft_id)
 BEGIN SELECT RAISE(ABORT,'submission and draft family mismatch'); END;
CREATE TRIGGER submission_family_update_check BEFORE UPDATE ON submissions
 WHEN NEW.manuscript_family_id != (SELECT manuscript_family_id FROM drafts WHERE draft_id=NEW.draft_id)
 BEGIN SELECT RAISE(ABORT,'submission and draft family mismatch'); END;
