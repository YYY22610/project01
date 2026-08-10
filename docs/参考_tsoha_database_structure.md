# Database structure（参考范例：vikketii/tsoha）

> 来源：https://github.com/vikketii/tsoha/blob/master/documentation/database_structure.md
> 用途：真实开源项目的独立数据库说明书范本，结构为「说明 → ER 图 → 建表 SQL → 逐表」。可对照本项目《数据库说明书》参考其组织方式。

There are seven tables with two junction tables in the database. Current database matches the programs needs, but there is room for improvements. For example I am not sure if it would be better to remove Song-Artist connection, and instead have Song-Featuring_Artist connection, because we can always get the main artist with connection Song-Album-Artist. But this could add more queries if we only want to search for Song and Artists.

## Database diagram

![database diagram](database_diagram.png)

## SQL for creating the tables

### 1. Account
```sql
CREATE TABLE account (
	id INTEGER NOT NULL,
	username VARCHAR(120) NOT NULL,
	password VARCHAR(200) NOT NULL,
	admin BOOLEAN NOT NULL,
	date_created DATETIME NOT NULL,
	PRIMARY KEY (id),
	CHECK (admin IN (0, 1))
);
```

### 2. Album
```sql
CREATE TABLE album (
	id INTEGER NOT NULL,
	name VARCHAR(120) NOT NULL,
	release_year INTEGER,
	PRIMARY KEY (id)
);
```

### 3. Artist
```sql
CREATE TABLE artist (
	id INTEGER NOT NULL,
	name VARCHAR(120) NOT NULL,
	PRIMARY KEY (id)
);
```

### 4. Song
```sql
CREATE TABLE song (
	id INTEGER NOT NULL,
	name VARCHAR(120) NOT NULL,
	views INTEGER NOT NULL,
	account_id INTEGER NOT NULL,
	album_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(account_id) REFERENCES account (id),
	FOREIGN KEY(album_id) REFERENCES album (id)
);
```

### 5. Sample
```sql
CREATE TABLE sample (
	id INTEGER NOT NULL,
	original_id INTEGER NOT NULL,
	used_id INTEGER NOT NULL,
	original_start TIME NOT NULL,
	used_start TIME NOT NULL,
	views INTEGER NOT NULL,
	account_id INTEGER NOT NULL,
	date_created DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(original_id) REFERENCES song (id),
	FOREIGN KEY(used_id) REFERENCES song (id),
	FOREIGN KEY(account_id) REFERENCES account (id)
);
```

### 6. Album_artist
```sql
CREATE TABLE album_artist (
	artist_id INTEGER NOT NULL,
	album_id INTEGER NOT NULL,
	PRIMARY KEY (artist_id, album_id),
	FOREIGN KEY(artist_id) REFERENCES artist (id),
	FOREIGN KEY(album_id) REFERENCES album (id)
);
```

### 7. Song_artist
```sql
CREATE TABLE song_artist (
	artist_id INTEGER NOT NULL,
	song_id INTEGER NOT NULL,
	PRIMARY KEY (artist_id, song_id),
	FOREIGN KEY(artist_id) REFERENCES artist (id),
	FOREIGN KEY(song_id) REFERENCES song (id)
);
```

---

**对本书项目《数据库说明书》的借鉴点**：
- 它是一份**独立成篇**的 `database_structure.md`，而非散落在 README；开头先讲「设计现状与可改进点」，再给 ER 图，再给 SQL，最后是逐表——这种「先全局后局部」的顺序值得参考。
- 关联表（album_artist / song_artist）采用**双外键联合主键、无独立自增 ID**，与你计划把 `admin_scores` 改为 `(user_id, scorer)` 联合唯一的思路一致。
