# Table: [main](..).[Genre]
<no value>

```
USE chinook;
SELECT * FROM main.Genre;
```



## Primary key
`PK_Genre` (**GenreId**)

## Foreign keys
*None*

## Columns
- `GenreId` INTEGER
  - *Indexes*: `IPK_Genre`
- `Name` NVARCHAR(120)

## Indexes
- IPK_Genre (GenreId) `` - `UNIQUE`

## Referenced by

- [main](../../../main).[Track](../../../main/tables/Track)
  - `FK_Track2{Genre true}_GenreId`
    <br>by columns: `GenreId` &mdash;
    <small>JOIN:
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Genre%0ALEFT+JOIN+main.Track+ON+Track.GenreId+%3D+Genre.GenreId' target='_blank'>LEFT</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Genre%0AINNER+JOIN+main.Track+ON+Track.GenreId+%3D+Genre.GenreId' target='_blank'>INNER</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.Genre%0ARIGHT+JOIN+main.Track+ON+Track.GenreId+%3D+Genre.GenreId' target='_blank'>RIGHT</a>
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

