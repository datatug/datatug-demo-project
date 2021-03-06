# Table: [main](..).[Album]
<no value>

```
USE chinook;
SELECT * FROM main.Album;
```



## Primary key
`PK_Album` (**AlbumId**)

## Foreign keys
- `FK_Album2{Artist true}_ArtistId` (**ArtistId**) ⇒ [main](../../../main).[Artist](../../../main/tables/Artist)
  <br>&nbsp;&nbsp;SQL *to* JOIN: <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Album%0ALEFT+JOIN+main.Artist+ON+Artist.ArtistId+%3D+Album.ArtistId' target='_blank'>LEFT</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Album%0AINNER+JOIN+main.Artist+ON+Artist.ArtistId+%3D+Album.ArtistId' target='_blank'>INNER</a> | <a href='https://datatug.app/query#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Album%0ARIGHT+JOIN+main.Artist+ON+Artist.ArtistId+%3D+Album.ArtistId' target='_blank'>RIGHT</a>

## Columns
- `AlbumId` INTEGER
  - *Indexes*: `IPK_Album`
- `Title` NVARCHAR(160)
- `ArtistId` INTEGER
  - *Indexes*: `IFK_AlbumArtistId`
  - *Foreign key*: `FK_Album2{Artist true}_ArtistId`

## Indexes
- IFK_AlbumArtistId (ArtistId) ``
- IPK_Album (AlbumId) `` - `UNIQUE`

## Referenced by

- [main](../../../main).[Track](../../../main/tables/Track)
  - `FK_Track2{Album true}_AlbumId`
    <br>by columns: `AlbumId` &mdash;
    <small>JOIN:
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Album%0ALEFT+JOIN+main.Track+ON+Track.AlbumId+%3D+Album.AlbumId' target='_blank'>LEFT</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Album%0AINNER+JOIN+main.Track+ON+Track.AlbumId+%3D+Album.AlbumId' target='_blank'>INNER</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Album%0ARIGHT+JOIN+main.Track+ON+Track.AlbumId+%3D+Album.AlbumId' target='_blank'>RIGHT</a>
    </small>

  - Referenced by:

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

