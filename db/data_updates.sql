select * from event_observations where video_file like "%m.mp4";
delete from event_observations where video_file like "%m.mp4";

select label, count(*) from event_classifications where is_deprecated is null GROUP BY 1 order by 2 desc;

update event_classifications set is_deprecated = true where label in ('night', 'driveby', 'walkby', 'wind', 'driveway activity', 'cloud change', 'arrive', 'departure', 're-adjust camera', 'lighting change');
update event_classifications set label = 'precipitation' where  label in ('snow', 'rain');
update event_classifications set label = 'lights, decorative' where label = 'lights- christmas';

select distinct label from event_classifications where (label like '% %') and is_deprecated is null;

update event_classifications set label = 'pedestrian' where label = 'pedestrian ';
update event_classifications set label = 'bicycle' where label = 'bicycle ';
update event_classifications set label = 'tree-branches' where label = 'tree branches';
update event_classifications set label = 'lights-decorative' where label = 'lights, decorative';
update event_classifications set label = 'lighting-scene' where label = 'lighting, scene' ;

delete from motion_events where id in (
select id from (
select
id,
width*height as area
from motion_events ) as t where t.area = 0);

update event_observations set video_location = replace(video_location, '/data/video/', '') where video_location like '/data/video/%';

UPDATE event_observations SET lighting_type='twilight' WHERE lighting_type='twighlight';