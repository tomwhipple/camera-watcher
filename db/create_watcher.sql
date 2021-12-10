
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