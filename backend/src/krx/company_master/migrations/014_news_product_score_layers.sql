ALTER TABLE normalized_events ADD COLUMN materiality_score REAL NOT NULL DEFAULT 0;
ALTER TABLE normalized_events ADD COLUMN editorial_score REAL NOT NULL DEFAULT 0;

ALTER TABLE news_cards ADD COLUMN materiality_score REAL NOT NULL DEFAULT 0;
ALTER TABLE news_cards ADD COLUMN editorial_score REAL NOT NULL DEFAULT 0;
