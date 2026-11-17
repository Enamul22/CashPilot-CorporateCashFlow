-- CashPilot schema v1; apply through cashpilot migrate (also registers immutable forecasts).

CREATE TABLE cp_forecasts (
	id VARCHAR(64) NOT NULL, 
	account_id VARCHAR(30) NOT NULL, 
	origin VARCHAR(10) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	body TEXT NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE cp_schema (
	id SERIAL NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE cp_workspaces (
	token_hash VARCHAR(64) NOT NULL, 
	generation INTEGER NOT NULL, 
	created_at VARCHAR(40) NOT NULL, 
	PRIMARY KEY (token_hash)
)

;

CREATE TABLE cp_events (
	id SERIAL NOT NULL, 
	workspace VARCHAR(64) NOT NULL, 
	forecast_id VARCHAR(64) NOT NULL, 
	account_id VARCHAR(30) NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	created_at VARCHAR(40) NOT NULL, 
	intent VARCHAR(64) NOT NULL, 
	body TEXT NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace, intent), 
	FOREIGN KEY(workspace) REFERENCES cp_workspaces (token_hash), 
	FOREIGN KEY(forecast_id) REFERENCES cp_forecasts (id)
)

;
INSERT INTO cp_schema (id, version) VALUES (1, 1) ON CONFLICT (id) DO NOTHING;
