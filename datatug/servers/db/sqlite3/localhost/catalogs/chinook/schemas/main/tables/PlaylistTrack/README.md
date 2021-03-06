# Table: [main](..).[PlaylistTrack]
<no value>

```
USE chinook;
SELECT * FROM main.PlaylistTrack;
```



## Primary key
`PK_PlaylistTrack` (**PlaylistId**, **TrackId**)

## Foreign keys
- `FK_PlaylistTrack2{Track true}_TrackId` (**TrackId**) ⇒ [main](../../../main).[Track](../../../main/tables/Track)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.PlaylistTrack%0ALEFT+JOIN+main.Track+ON+Track.TrackId+%3D+PlaylistTrack.TrackId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.PlaylistTrack%0AINNER+JOIN+main.Track+ON+Track.TrackId+%3D+PlaylistTrack.TrackId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.PlaylistTrack%0ARIGHT+JOIN+main.Track+ON+Track.TrackId+%3D+PlaylistTrack.TrackId' target='_blank'>RIGHT</a>
- `FK_PlaylistTrack2{Playlist true}_PlaylistId` (**PlaylistId**) ⇒ [main](../../../main).[Playlist](../../../main/tables/Playlist)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.PlaylistTrack%0ALEFT+JOIN+main.Playlist+ON+Playlist.PlaylistId+%3D+PlaylistTrack.PlaylistId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.PlaylistTrack%0AINNER+JOIN+main.Playlist+ON+Playlist.PlaylistId+%3D+PlaylistTrack.PlaylistId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.PlaylistTrack%0ARIGHT+JOIN+main.Playlist+ON+Playlist.PlaylistId+%3D+PlaylistTrack.PlaylistId' target='_blank'>RIGHT</a>

## Columns
- `PlaylistId` INTEGER
  - *Indexes*: `IPK_PlaylistTrack`, `sqlite_autoindex_PlaylistTrack_1`
  - *Foreign key*: `FK_PlaylistTrack2{Playlist true}_PlaylistId`
- `TrackId` INTEGER
  - *Indexes*: `IFK_PlaylistTrackTrackId`, `IPK_PlaylistTrack`, `sqlite_autoindex_PlaylistTrack_1`
  - *Foreign key*: `FK_PlaylistTrack2{Track true}_TrackId`

## Indexes
- IFK_PlaylistTrackTrackId (TrackId) ``
- IPK_PlaylistTrack (PlaylistId, TrackId) `` - `UNIQUE`
- sqlite_autoindex_PlaylistTrack_1 (PlaylistId, TrackId) `` - `PRIMARY KEY`

## Referenced by
*None*

