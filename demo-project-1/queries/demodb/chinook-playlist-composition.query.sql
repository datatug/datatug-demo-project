SELECT
    p.PlaylistId,
    p.Name AS Playlist,
    COUNT(DISTINCT pt.TrackId) AS TrackCount,
    COUNT(DISTINCT t.AlbumId) AS AlbumCount
FROM Playlist p
JOIN PlaylistTrack pt
    ON pt.PlaylistId = p.PlaylistId
JOIN Track t
    ON t.TrackId = pt.TrackId
GROUP BY p.PlaylistId,p.Name
ORDER BY TrackCount DESC,p.PlaylistId
LIMIT 10
