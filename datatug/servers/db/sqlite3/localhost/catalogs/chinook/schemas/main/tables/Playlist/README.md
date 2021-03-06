# Table: [main](..).[Playlist]
<no value>

```
USE chinook;
SELECT * FROM main.Playlist;
```



## Primary key
`PK_Playlist` (**PlaylistId**)

## Foreign keys
*None*

## Columns
- `PlaylistId` INTEGER
  - *Indexes*: `IPK_Playlist`
- `Name` NVARCHAR(120)

## Indexes
- IPK_Playlist (PlaylistId) `` - `UNIQUE`

## Referenced by

- [main](../../../main).[PlaylistTrack](../../../main/tables/PlaylistTrack)
  - `FK_PlaylistTrack2{Playlist true}_PlaylistId`
    <br>by columns: `PlaylistId` &mdash;
    <small>JOIN:
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Playlist%0ALEFT+JOIN+main.PlaylistTrack+ON+PlaylistTrack.PlaylistId+%3D+Playlist.PlaylistId' target='_blank'>LEFT</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Playlist%0AINNER+JOIN+main.PlaylistTrack+ON+PlaylistTrack.PlaylistId+%3D+Playlist.PlaylistId' target='_blank'>INNER</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Playlist%0ARIGHT+JOIN+main.PlaylistTrack+ON+PlaylistTrack.PlaylistId+%3D+Playlist.PlaylistId' target='_blank'>RIGHT</a>
    </small>

