
CREATE TABLE IF NOT EXISTS event_observations (
	id SERIAL,
	video_file VARCHAR(75),
	capture_time DATETIME,
	scene_name VARCHAR(20),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS event_classifications (
	id SERIAL,
	observation_id BIGINT UNSIGNED NOT NULL,
	usefullness ENUM('USELESS', 'INTERESTING'), 
	decider VARCHAR(10),
	decision_time TIMESTAMP,
	confidence DOUBLE,
	PRIMARY KEY(id),
	FOREIGN KEY (observation_id)
		REFERENCES event_observations(id)
		ON DELETE CASCADE
);

ALTER TABLE event_observations
	ADD COLUMN IF NOT EXISTS storage_local BOOLEAN null,
 	ADD COLUMN IF NOT EXISTS storage_gcloud BOOLEAN null;
 	
ALTER TABLE event_observations
	ADD UNIQUE INDEX IF NOT EXISTS idx_video_file (video_file);
	
CREATE TABLE IF NOT EXISTS api_users (
	id SERIAL,
	username VARCHAR(128),
	key_hash VARCHAR(256)
);

ALTER TABLE event_classifications DROP COLUMN IF EXISTS usefullness;
ALTER TABLE event_classifications ADD COLUMN IF NOT EXISTS label varchar(20);

ALTER TABLE event_classifications ADD UNIQUE labeling (observation_id, label, decider);

ALTER TABLE event_classifications MODIFY COLUMN label varchar(20) NOT NULL;

ALTER TABLE event_observations ADD COLUMN IF NOT EXISTS video_location varchar(100);

ALTER TABLE event_classifications ADD COLUMN IF NOT EXISTS is_deprecated BOOLEAN;

CREATE TABLE IF NOT EXISTS motion_events (
	id SERIAL,
	observation_id BIGINT UNSIGNED NOT NULL,
	frame BIGINT,
	x INT,
	y INT,
	width INT,
	height INT,
	pixels INT,
	noise DOUBLE,
	PRIMARY KEY(id),
	FOREIGN KEY(observation_id)
		REFERENCES event_observations(id)
		ON DELETE CASCADE
);

ALTER TABLE event_observations
	ADD COLUMN IF NOT EXISTS event_name varchar(20),
	ADD COLUMN IF NOT EXISTS threshold int,
	ADD COLUMN IF NOT EXISTS noise_level int,
	ADD UNIQUE INDEX IF NOT EXISTS idx_event_name (event_name);
	
ALTER TABLE motion_events
	ADD COLUMN IF NOT EXISTS label_count int,
	DROP COLUMN IF EXISTS noise,
	ADD COLUMN IF NOT EXISTS event_name varchar(20);
	
ALTER TABLE motion_events DROP CONSTRAINT IF EXISTS motion_events_ibfk_1;

ALTER TABLE motion_events DROP COLUMN IF EXISTS observation_id;

ALTER TABLE motion_events
	ADD INDEX IF NOT EXISTS idx_event_name_on_motion_events (event_name);

ALTER TABLE event_observations ADD COLUMN IF NOT EXISTS lighting_type varchar(10);

ALTER TABLE event_observations MODIFY COLUMN event_name VARCHAR(100);
ALTER TABLE motion_events MODIFY COLUMN event_name VARCHAR(100);

CREATE TABLE IF NOT EXISTS uploads (
	sync_at TIMESTAMP,
	event_id BIGINT UNSIGNED NOT NULL,
	event_type VARCHAR(20),
	result_code INT
);

ALTER TABLE uploads ADD INDEX upload_idx (event_id, event_type);
ALTER TABLE uploads
	ADD COLUMN IF NOT EXISTS id SERIAL,
	ADD PRIMARY KEY(id);

CREATE TABLE IF NOT EXISTS computations (
	id SERIAL,
	event_name VARCHAR(100),
	method_name VARCHAR(30),
	computed_at TIMESTAMP,
	elapsed_seconds DOUBLE,
	git_version VARCHAR(20),
	host_info TINYTEXT,
	success BOOLEAN NOT NULL,
	result LONGTEXT,
	result_file VARCHAR(100),
	result_file_location VARCHAR(100)
);

ALTER TABLE uploads
	CHANGE COLUMN event_id object_id BIGINT UNSIGNED NOT NULL,
	CHANGE COLUMN event_type object_class VARCHAR(20),
	CHANGE COLUMN result_code http_status SMALLINT,
	ADD COLUMN upload_batch VARCHAR(40)
;
	
