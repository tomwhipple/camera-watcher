# Camera Watcher

Uses Flask for backend. 



[API index endpoint](https://home.tomwhipple.com/watcher/get_uncategorized)

Control script:

```
watcher.py -h
```

Data load:

```
kerberos/scripts/watcher.py upload_dir -d /data/video/wellerDrive/capture | xargs -I{} mv {} /data/video/wellerDrive/capture/jsonl/
```



## TODO

- API authentication
- iOS app for classification