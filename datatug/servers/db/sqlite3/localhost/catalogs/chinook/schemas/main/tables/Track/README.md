# Table: [main](..).[Track]
<no value>

```
USE chinook;
SELECT * FROM main.Track;
```



## Primary key
`PK_Track` (**TrackId**)

## Foreign keys
- `FK_Track2{MediaType true}_MediaTypeId` (**MediaTypeId**) ⇒ [main](../../../main).[MediaType](../../../main/tables/MediaType)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0ALEFT+JOIN+main.MediaType+ON+MediaType.MediaTypeId+%3D+Track.MediaTypeId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0AINNER+JOIN+main.MediaType+ON+MediaType.MediaTypeId+%3D+Track.MediaTypeId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0ARIGHT+JOIN+main.MediaType+ON+MediaType.MediaTypeId+%3D+Track.MediaTypeId' target='_blank'>RIGHT</a>
- `FK_Track2{Genre true}_GenreId` (**GenreId**) ⇒ [main](../../../main).[Genre](../../../main/tables/Genre)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0ALEFT+JOIN+main.Genre+ON+Genre.GenreId+%3D+Track.GenreId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0AINNER+JOIN+main.Genre+ON+Genre.GenreId+%3D+Track.GenreId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0ARIGHT+JOIN+main.Genre+ON+Genre.GenreId+%3D+Track.GenreId' target='_blank'>RIGHT</a>
- `FK_Track2{Album true}_AlbumId` (**AlbumId**) ⇒ [main](../../../main).[Album](../../../main/tables/Album)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0ALEFT+JOIN+main.Album+ON+Album.AlbumId+%3D+Track.AlbumId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0AINNER+JOIN+main.Album+ON+Album.AlbumId+%3D+Track.AlbumId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0ARIGHT+JOIN+main.Album+ON+Album.AlbumId+%3D+Track.AlbumId' target='_blank'>RIGHT</a>

## Columns
- `TrackId` INTEGER
  - *Indexes*: `IPK_Track`
- `Name` NVARCHAR(200)
- `AlbumId` INTEGER
  - *Indexes*: `IFK_TrackAlbumId`
  - *Foreign key*: `FK_Track2{Album true}_AlbumId`
- `MediaTypeId` INTEGER
  - *Indexes*: `IFK_TrackMediaTypeId`
  - *Foreign key*: `FK_Track2{MediaType true}_MediaTypeId`
- `GenreId` INTEGER
  - *Indexes*: `IFK_TrackGenreId`
  - *Foreign key*: `FK_Track2{Genre true}_GenreId`
- `Composer` NVARCHAR(220)
- `Milliseconds` INTEGER
- `Bytes` INTEGER
- `UnitPrice` NUMERIC(10,2)

## Indexes
- IFK_TrackMediaTypeId (MediaTypeId) ``
- IFK_TrackGenreId (GenreId) ``
- IFK_TrackAlbumId (AlbumId) ``
- IPK_Track (TrackId) `` - `UNIQUE`

## Referenced by

- [main](../../../main).[InvoiceLine](../../../main/tables/InvoiceLine)
  - `FK_InvoiceLine2{Track true}_TrackId`
    <br>by columns: `TrackId` &mdash;
    <small>JOIN:
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0ALEFT+JOIN+main.InvoiceLine+ON+InvoiceLine.TrackId+%3D+Track.TrackId' target='_blank'>LEFT</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0AINNER+JOIN+main.InvoiceLine+ON+InvoiceLine.TrackId+%3D+Track.TrackId' target='_blank'>INNER</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0ARIGHT+JOIN+main.InvoiceLine+ON+InvoiceLine.TrackId+%3D+Track.TrackId' target='_blank'>RIGHT</a>
    </small>

- [main](../../../main).[PlaylistTrack](../../../main/tables/PlaylistTrack)
  - `FK_PlaylistTrack2{Track true}_TrackId`
    <br>by columns: `TrackId` &mdash;
    <small>JOIN:
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0ALEFT+JOIN+main.PlaylistTrack+ON+PlaylistTrack.TrackId+%3D+Track.TrackId' target='_blank'>LEFT</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0AINNER+JOIN+main.PlaylistTrack+ON+PlaylistTrack.TrackId+%3D+Track.TrackId' target='_blank'>INNER</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Track%0ARIGHT+JOIN+main.PlaylistTrack+ON+PlaylistTrack.TrackId+%3D+Track.TrackId' target='_blank'>RIGHT</a>
    </small>

