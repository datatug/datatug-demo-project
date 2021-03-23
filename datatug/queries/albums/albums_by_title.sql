SELECT
    al.AlbumId,
    al.Title AS AlbumTitle,
    ar.ArtistId,
    ar.Name AS ArtistName,
    (SELECT COUNT(1) FROM Track AS t WHERE t.AlbumId = al.AlbumId) AS TracksCount,
    (SELECT COUNT(DISTINCT GenreId) FROM Track AS t WHERE t.AlbumId = al.AlbumId) AS GenresCount
FROM Album AS al
INNER JOIN Artist AS ar ON ar.ArtistId = al.ArtistId
WHERE al.ArtistId = IFNULL(@ArtistId, al.ArtistId)
ORDER BY Title