# Table: [main](..).[MediaType]
<no value>

```
USE chinook;
SELECT * FROM main.MediaType;
```



## Primary key
`PK_MediaType` (**MediaTypeId**)

## Foreign keys
*None*

## Columns
- `MediaTypeId` INTEGER
  - *Indexes*: `IPK_MediaType`
- `Name` NVARCHAR(120)

## Indexes
- IPK_MediaType (MediaTypeId) `` - `UNIQUE`

## Referenced by

- [main](../../../main).[Track](../../../main/tables/Track)
  - `FK_Track2{MediaType true}_MediaTypeId`
    <br>by columns: `MediaTypeId` &mdash;
    <small>JOIN:
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.MediaType%0ALEFT+JOIN+main.Track+ON+Track.MediaTypeId+%3D+MediaType.MediaTypeId' target='_blank'>LEFT</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.MediaType%0AINNER+JOIN+main.Track+ON+Track.MediaTypeId+%3D+MediaType.MediaTypeId' target='_blank'>INNER</a> |
    <a href='https://datatug.app/pwa/query?server=localhost&catalog=chinook#text=USE+chinook%0ASELECT%0A%09%2A%0AFROM+main.MediaType%0ARIGHT+JOIN+main.Track+ON+Track.MediaTypeId+%3D+MediaType.MediaTypeId' target='_blank'>RIGHT</a>
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

