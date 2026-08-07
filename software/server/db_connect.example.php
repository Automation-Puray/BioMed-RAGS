<?php
/*
 * Copy this file to db_connect.php and replace the placeholder values.
 * The real db_connect.php file is excluded from Git.
 */

$host = 'localhost';
$user = 'replace_with_database_user';
$password = 'replace_with_database_password';
$dbname = 'replace_with_database_name';

$conn = new mysqli($host, $user, $password, $dbname);

if ($conn->connect_error) {
    die('Database connection failed.');
}

$conn->set_charset('utf8mb4');
?>