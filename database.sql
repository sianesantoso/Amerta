CREATE DATABASE amerta;

USE amerta;

CREATE TABLE barang (
    kode_barang VARCHAR(10) PRIMARY KEY,
    nama_barang VARCHAR(255),
    jumlah INT,
    harga INT,
    supplier_aktif VARCHAR(100)
);

CREATE TABLE transaksi (
    id_transaksi INT AUTO_INCREMENT PRIMARY KEY,
    tanggal DATETIME,
    nama_pembeli VARCHAR(255),
    total_pembelian DECIMAL(10,2)
);

CREATE TABLE supplier (
    nama_supplier VARCHAR(255) PRIMARY KEY,
    alamat TEXT NULL,
    nomor_telepon VARCHAR(25) NULL
);

CREATE TABLE riwayat_pengisian_stok (
    id INT AUTO_INCREMENT PRIMARY KEY,
    kode_barang VARCHAR(10),
    jumlah_ditambahkan INT,
    supplier VARCHAR(100),
    tanggal DATETIME
);

