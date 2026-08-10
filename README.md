You can build this as a **MySQL Performance Monitoring & Query Intelligence Platform**. Below is a detailed development prompt you can give to an AI coding assistant to generate the Python application.

---

# Project Prompt: MySQL Query Profiler + Server Health Monitoring Application (Python)

## Objective

Build a production-grade Python application that continuously monitors MySQL/MariaDB databases, analyzes query performance, tracks server resource usage, stores historical metrics, and generates optimization reports.

The application should work as a long-running monitoring agent and provide historical analysis for future database tuning decisions.

---

# Technology Stack

Use:

* Python 3.12+
* FastAPI for backend API
* SQLAlchemy ORM
* MySQL Connector/Python
* SQLite/PostgreSQL for storing monitoring history
* psutil for OS metrics
* pandas for analysis
* matplotlib/plotly for graphs
* APScheduler for scheduled collectors
* Jinja2 for HTML reports
* Docker support

Optional:

* Redis for queue/cache
* Celery for distributed monitoring
* Prometheus exporter support

---

# Application Architecture

Create modules:

```
mysql-profiler/

├── app/
│   ├── main.py
│   ├── config.py
│
├── collectors/
│   ├── mysql_status.py
│   ├── slow_queries.py
│   ├── processlist.py
│   ├── performance_schema.py
│   └── system_metrics.py
│
├── analyzers/
│   ├── query_analyzer.py
│   ├── index_analyzer.py
│   ├── memory_analyzer.py
│   └── recommendation_engine.py
│
├── database/
│   ├── models.py
│   └── connection.py
│
├── reports/
│   ├── html_report.py
│   └── charts.py
│
├── scheduler/
│   └── jobs.py
│
├── api/
│   └── routes.py
│
└── storage/
```

---

# Database Monitoring Features

## 1. MySQL Connection Monitor

Support:

* MariaDB 10.x
* MySQL 8.x

Collect:

```
Server version
Database size
Table sizes
Connection count
Active queries
Uptime
Threads
Buffer pool status
```

Store:

```
mysql_servers

id
hostname
port
version
created_at
```

---

# 2. Slow Query Collector

Read:

```
slow_query_log
```

Capture:

* Query text
* Database
* User
* Execution time
* Lock time
* Rows examined
* Rows sent
* Timestamp

Database:

```
query_logs

id
server_id
query_hash
query_text
database_name

execution_time
lock_time

rows_examined
rows_sent

created_at
```

---

# 3. Query Fingerprinting

Normalize queries:

Example:

Before:

```sql
SELECT * FROM students WHERE id=100
```

After:

```sql
SELECT * FROM students WHERE id=?
```

Generate:

```
query_hash
```

Group similar queries.

Example:

```
Query:
student search

Calls:
250000

Total Time:
8 hours

Average:
120ms
```

---

# 4. Query Performance Ranking

Generate rankings:

## Most expensive queries

Sort by:

```
total_execution_time
```

Example:

```
Rank Query                 Time

1     attendance report    6h
2     student search       4h
3     fees calculation     2h
```

## Worst latency

Sort:

```
avg_execution_time
```

---

# 5. EXPLAIN Analyzer

For slow queries:

Automatically execute:

```sql
EXPLAIN FORMAT=JSON query
```

Analyze:

Detect:

* Full table scan
* Missing indexes
* Temporary tables
* Filesort
* Large row scans

Generate:

Example:

```
Problem:

Table:
student_information


Issue:
500000 rows scanned


Recommendation:

CREATE INDEX idx_student_id
ON student_information(student_id);
```

---

# 6. Memory Analysis

Calculate MySQL memory requirement.

Collect:

```
innodb_buffer_pool_size

max_connections

sort_buffer_size

join_buffer_size

read_buffer_size

tmp_table_size

max_heap_table_size
```

Calculate:

Formula:

```
Estimated Memory =
innodb_buffer_pool
+
(max_connections × per_connection_memory)
+
temporary_buffers
```

Generate:

Example:

```
Current:

RAM:
16GB

MySQL Possible Usage:

21GB


Risk:
High memory pressure
```

---

# 7. InnoDB Health Monitoring

Collect:

```sql
SHOW ENGINE INNODB STATUS
```

Parse:

Monitor:

* Deadlocks
* Buffer pool hit ratio
* Dirty pages
* Pending writes
* History list length

Store:

```
innodb_metrics

buffer_hit_ratio

deadlocks

dirty_pages

pending_io

created_at
```

---

# 8. OS Health Monitoring

Using psutil collect:

## CPU

```
cpu_percent

load_average

cpu_frequency
```

## Memory

```
total_ram

used_ram

available_ram

swap_usage
```

## Disk

```
disk_usage

disk_read

disk_write

iops
```

## Network

```
bytes_sent

bytes_received
```

Store every:

```
5 seconds
```

Table:

```
system_metrics

cpu

memory

disk_read

disk_write

network_in

network_out

timestamp
```

---

# 9. Process Monitoring

Track:

MySQL process:

```
mysqld
mariadbd
```

Collect:

```
CPU usage

RAM usage

threads

open files
```

---

# 10. Alert System

Create rules:

Example:

## High CPU

```
CPU > 90%
for 5 minutes
```

Alert:

```
Database server CPU critical
```

---

## Slow Query

```
execution_time > 5 sec
```

Alert:

```
Query taking too long
```

---

## Memory

```
Available RAM < 10%
```

---

# 11. Dashboard

Create FastAPI + HTML dashboard.

Pages:

## Overview

Show:

```
CPU
RAM
Disk
MySQL Connections
Slow Queries
Database Size
```

---

## Query Dashboard

Graphs:

* Slowest queries
* Most executed queries
* Total query time
* Query trends

---

## Server Health

Charts:

```
CPU usage
RAM usage
Disk IO
Network
```

---

# 12. Scheduled Jobs

Using APScheduler:

Every 5 seconds:

```
collect system metrics
```

Every minute:

```
collect mysql status
collect processlist
```

Every hour:

```
analyze queries
generate recommendations
```

Daily:

```
generate HTML report
```

---

# 13. Report Generator

Generate:

```
mysql-report-2026-08-10.html
```

Include:

## Summary

```
Database Health Score: 82/100
```

## Problems

```
5 slow queries detected

3 missing indexes

Memory pressure detected
```

## Recommendations

```
Increase innodb_buffer_pool_size

Add index:

table.column
```

---

# 14. Security Requirements

* Never store database passwords plain text
* Encrypt credentials
* Read from environment variables
* Role-based API authentication
* Query masking for sensitive data

---

# 15. Deployment

Support:

Docker:

```
docker compose up -d
```

Services:

```
mysql-profiler-api
mysql-profiler-worker
mysql-profiler-db
```

---

# 16. Future Features

Prepare architecture for:

* Multiple MySQL servers
* Cloud monitoring
* AI query optimization
* Automatic index suggestion
* Query regression detection
* Before/after tuning comparison
* Capacity planning

---

# Initial MVP Development Order

Build in this order:

1. System metrics collector
2. MySQL status collector
3. Slow query parser
4. SQLite storage
5. Query ranking engine
6. HTML report
7. FastAPI dashboard
8. Alert system
9. AI recommendations

---

This design will become similar to a lightweight combination of **Percona Monitoring and Management + MySQLTuner + custom ERP performance analytics**, but tailored for your MariaDB/ERP environment.
