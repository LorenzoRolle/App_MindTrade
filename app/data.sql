
CREATE TABLE IF NOT EXISTS utenti(
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  email VARCHAR(100) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS NOTIFICA(
  NomeAss VARCHAR(50) NOT NULL,
  Direction VARCHAR(6) NOT NULL,
  PositionSize INT NOT NULL,
  EntryPrice INT NOT NULL,
  StopLoss INT, -- non ho capito se sia un numero o che cos'altro, nel dubbio metto int
  TakeProfit INT,
  RFT TEXT, --reason for trade
  Conf TINYINT CHECK (Conf BETWEEN 0 AND 100),
  Emotion VARCHAR(15),
  Planned VARCHAR(4)
);
