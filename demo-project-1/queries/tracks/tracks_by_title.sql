SELECT
    t.*,
    g.Name as GenreName,
    al.Title AS AlbumTitle,
    ar.ArtistId,
    ar.Name AS ArtistName
FROM Track AS t
INNER JOIN Album AS al ON al.AlbumID = t.AlbumID
INNER JOIN Artist AS ar ON ar.ArtistId = al.ArtistId
INNER JOIN Genre AS g ON g.GenreId = t.GenreId
WHERE t.GenreId = IFNULL(t.GenreId, t.GenreId)
  AND t.AlbumId = IFNULL(@AlbumId, t.AlbumId)
  AND al.ArtistId = IFNULL(@ArtistId, al.ArtistId)
ORDER BY Title