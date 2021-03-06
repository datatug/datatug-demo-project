# Table: [main](..).[Artist]
<no value>

```
USE chinook;
SELECT * FROM main.Artist;
```



## Primary key
`PK_Artist` (**ArtistId**)

## Foreign keys
*None*

## Columns
- `ArtistId` INTEGER
  - *Indexes*: `IPK_Artist`
- `Name` NVARCHAR(120)

## Indexes
- IPK_Artist (ArtistId) `` - `UNIQUE`

## Referenced by

- [main](../../../main).[Album](../../../main/tables/Album)
  - `FK_Album2{Artist true}_ArtistId`
    <br>by columns: `ArtistId` &mdash;
    <small>JOIN:
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Artist%0ALEFT+JOIN+main.Album+ON+Album.ArtistId+%3D+Artist.ArtistId' target='_blank'>LEFT</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Artist%0AINNER+JOIN+main.Album+ON+Album.ArtistId+%3D+Artist.ArtistId' target='_blank'>INNER</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Artist%0ARIGHT+JOIN+main.Album+ON+Album.ArtistId+%3D+Artist.ArtistId' target='_blank'>RIGHT</a>
    </small>

  - Referenced by:

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

