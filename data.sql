
CREATE TABLE UTENTE(
  username VARCHAR(50) PRIMARY KEY NOT NULL UNIQUE,
  email VARCHAR(30) NOT NULL UNIQUE,
  password VARCHAR(55) NOT NULL
);


CREATE TABLE NOTIFICA (
  email VARCHAR(30) NOT NULL,
  FOREIGN KEY (email) REFERENCES UTENTE(email),
  entry_price DECIMAL(10, 2) NOT NULL,
  exit_price DECIMAL(10, 2) NOT NULL,
  entry_timestamp TIMESTAMP PRIMARY KEY NOT NULL,
  exit_timestamp TIMESTAMP NOT NULL,
  account_size DECIMAL(15, 2) NOT NULL,
  fraction_invested DECIMAL(5, 4) NOT NULL,
  notes TEXT NOT NULL,
  asset_type VARCHAR(10) CHECK (asset_type IN ('Stock', 'ETF', 'Crypto', 'Forex'))
);

