-- MariaDB dump 10.19  Distrib 10.5.19-MariaDB, for debian-linux-gnu (aarch64)
--
-- Host: localhost    Database: watcher
-- ------------------------------------------------------
-- Server version	10.5.19-MariaDB-0+deb11u2
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO,ANSI' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table "api_users"
--

DROP TABLE IF EXISTS "api_users";
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE "api_users" (
  "id" INTEGER PRIMARY KEY NOT NULL,
  "username" varchar(128) DEFAULT NULL,
  "key_hash" varchar(256) DEFAULT NULL
);
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table "computations"
--

DROP TABLE IF EXISTS "computations";
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE "computations" (
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table "event_classifications"
--

DROP TABLE IF EXISTS "event_classifications";
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE "event_classifications" (
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table "event_observations"
--

DROP TABLE IF EXISTS "event_observations";
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE "event_observations" (
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
--
-- Table structure for table "uploads"
--

DROP TABLE IF EXISTS "uploads";
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE "uploads" (
  "id" INTEGER PRIMARY KEY NOT NULL,
  "sync_at" timestamp NOT NULL,
  "object_id" INTEGER  NOT NULL,
  "object_class" varchar(20) DEFAULT NULL,
  "http_status" smallint(6) DEFAULT NULL,
  "upload_batch" varchar(40) DEFAULT NULL
);
CREATE INDEX "upload_idx" ON "uploads" ("object_id","object_class");
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table "weather"
--

DROP TABLE IF EXISTS "weather";
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE "weather" (
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
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2023-08-06 15:16:32

CREATE TABLE "labelings" (
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
