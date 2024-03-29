CREATE TABLE IF NOT EXISTS "api_users" (
  "id" INTEGER PRIMARY KEY NOT NULL,
  "username" varchar(128) DEFAULT NULL,
  "key_hash" varchar(256) DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS "computations" (
  "id" INTEGER PRIMARY KEY NOT NULL,
  "event_name" varchar(100) DEFAULT NULL,
  "method_name" varchar(30) DEFAULT NULL,
  "computed_at" timestamp NOT NULL , 
  "elapsed_seconds" double DEFAULT NULL,
  "git_version" varchar(20) DEFAULT NULL,
  "host_info" tinytext DEFAULT NULL,
  "success" tinyint(1) NOT NULL,
  "result" longtext DEFAULT NULL,
  "result_file" varchar(100) DEFAULT NULL,
  "result_file_location" varchar(100) DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS "event_classifications" (
  "id" INTEGER PRIMARY KEY NOT NULL,
  "observation_id" INTEGER  NOT NULL,
  "decider" varchar(10) DEFAULT NULL,
  "decision_time" timestamp NOT NULL,
  "confidence" double DEFAULT NULL,
  "label" varchar(20) NOT NULL,
  "is_deprecated" tinyint(1) DEFAULT NULL,
  CONSTRAINT "event_classifications_ibfk_1" FOREIGN KEY ("observation_id") REFERENCES "event_observations" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX "labeling" ON "event_classifications" ("observation_id","label","decider");
CREATE TABLE IF NOT EXISTS "event_observations" (
  "id" INTEGER PRIMARY KEY NOT NULL,
  "video_file" varchar(75) UNIQUE DEFAULT NULL,
  "capture_time" datetime DEFAULT NULL,
  "scene_name" varchar(20) DEFAULT NULL,
  "storage_local" tinyint(1) DEFAULT NULL,
  "storage_gcloud" tinyint(1) DEFAULT NULL,
  "video_location" varchar(100) DEFAULT NULL,
  "event_name" varchar(100) UNIQUE NOT NULL,
  "noise_level" int(11) DEFAULT NULL,
  "threshold" int(11) DEFAULT NULL,
  "lighting_type" varchar(10) DEFAULT NULL,
  "weather_id" INTEGER  DEFAULT NULL,
  -- UNIQUE KEY "id" ("id"),
  -- UNIQUE KEY "idx_video_file" ("video_file"),
  -- UNIQUE KEY "idx_event_name" ("event_name"),
  -- KEY "weather_id" ("weather_id"),
  CONSTRAINT "event_observations_ibfk_1" FOREIGN KEY ("weather_id") REFERENCES "weather" ("id")
);

CREATE TABLE IF NOT EXISTS "uploads" (
  "id" INTEGER PRIMARY KEY NOT NULL,
  "sync_at" timestamp NOT NULL,
  "object_id" INTEGER  NOT NULL,
  "object_class" varchar(20) DEFAULT NULL,
  "http_status" smallint(6) DEFAULT NULL,
  "upload_batch" varchar(40) DEFAULT NULL
);
CREATE INDEX "upload_idx" ON "uploads" ("object_id","object_class");
CREATE TABLE IF NOT EXISTS "weather" (
  "id" INTEGER PRIMARY KEY NOT NULL,
  "valid_at" timestamp NOT NULL,
  "valid_at_tz_offset_min" int(11) DEFAULT NULL,
  "description" text DEFAULT NULL,
  "temp_c" float DEFAULT NULL,
  "feels_like_c" float DEFAULT NULL,
  "temp_min_c" float DEFAULT NULL,
  "temp_max_c" float DEFAULT NULL,
  "pressure_hpa" int(11) DEFAULT NULL,
  "humid_pct" int(11) DEFAULT NULL,
  "wind_speed" float DEFAULT NULL,
  "wind_dir" int(11) DEFAULT NULL,
  "cloud_pct" int(11) DEFAULT NULL,
  "visibility" int(11) DEFAULT NULL
);
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
CREATE TABLE intermediate_results (
    id INTEGER NOT NULL, 
    computed_at DATETIME NOT NULL, 
    step VARCHAR NOT NULL, 
    info JSON, 
    file TEXT, 
    event_id INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(event_id) REFERENCES event_observations (id)
);
CREATE TABLE labelings (
    id INTEGER NOT NULL, 
    decider VARCHAR NOT NULL, 
    decided_at DATETIME NOT NULL, 
    labels JSON NOT NULL, 
    mask JSON, 
    probabilities JSON, 
    event_id INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(event_id) REFERENCES event_observations (id)
);
