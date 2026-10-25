-- Chinook teaching extract. SQLite 3.25+ (window functions).
-- Exact values from DataTug showcase chinook.sqlite; dates in this source are 2021-2025.
-- Deliberately limited population: CustomerId 1-4; all invoices of CustomerId 1-3.
-- Customer 4 has NO invoices IN THIS EXTRACT, not in the complete Chinook database.
-- Only columns used by these lessons are retained. Monetary amounts are dataset units.
PRAGMA foreign_keys = ON;
CREATE TABLE Customer (CustomerId INTEGER PRIMARY KEY, FirstName TEXT NOT NULL, LastName TEXT NOT NULL, Country TEXT);
CREATE TABLE Invoice (InvoiceId INTEGER PRIMARY KEY, CustomerId INTEGER NOT NULL REFERENCES Customer(CustomerId), InvoiceDate TEXT NOT NULL, Total NUMERIC NOT NULL);
INSERT INTO Customer (CustomerId, FirstName, LastName, Country) VALUES (1, 'Luís', 'Gonçalves', 'Brazil');
INSERT INTO Customer (CustomerId, FirstName, LastName, Country) VALUES (2, 'Leonie', 'Köhler', 'Germany');
INSERT INTO Customer (CustomerId, FirstName, LastName, Country) VALUES (3, 'François', 'Tremblay', 'Canada');
INSERT INTO Customer (CustomerId, FirstName, LastName, Country) VALUES (4, 'Bjørn', 'Hansen', 'Norway');
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (1, 2, '2021-01-01 00:00:00', 1.98);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (12, 2, '2021-02-11 00:00:00', 13.86);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (67, 2, '2021-10-12 00:00:00', 8.91);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (98, 1, '2022-03-11 00:00:00', 3.98);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (99, 3, '2022-03-11 00:00:00', 3.98);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (110, 3, '2022-04-21 00:00:00', 13.86);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (121, 1, '2022-06-13 00:00:00', 3.96);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (143, 1, '2022-09-15 00:00:00', 5.94);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (165, 3, '2022-12-20 00:00:00', 8.91);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (195, 1, '2023-05-06 00:00:00', 0.99);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (196, 2, '2023-05-19 00:00:00', 1.98);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (219, 2, '2023-08-21 00:00:00', 3.96);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (241, 2, '2023-11-23 00:00:00', 5.94);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (293, 2, '2024-07-13 00:00:00', 0.99);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (294, 3, '2024-07-26 00:00:00', 1.98);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (316, 1, '2024-10-27 00:00:00', 1.98);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (317, 3, '2024-10-28 00:00:00', 3.96);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (327, 1, '2024-12-07 00:00:00', 13.86);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (339, 3, '2025-01-30 00:00:00', 5.94);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (382, 1, '2025-08-07 00:00:00', 8.91);
INSERT INTO Invoice (InvoiceId, CustomerId, InvoiceDate, Total) VALUES (391, 3, '2025-09-20 00:00:00', 0.99);
