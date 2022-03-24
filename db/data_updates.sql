select * from event_observations where video_file like "%m.mp4";
delete from event_observations where video_file like "%m.mp4";

select label, count(*) from event_classifications where is_deprecated is null GROUP BY 1 order by 2 desc;

update event_classifications set is_deprecated = true where label in ('night', 'driveby', 'walkby', 'wind', 'driveway activity', 'cloud change', 'arrive', 'departure', 're-adjust camera', 'lighting change');
update event_classifications set label = 'precipitation' where  label in ('snow', 'rain');
update event_classifications set label = 'lights, decorative' where label = 'lights- christmas';