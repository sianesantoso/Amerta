from flask import Flask, render_template, request, redirect, flash, url_for, send_file, session
import mysql.connector
from datetime import datetime
import pandas as pd
import bcrypt
import io

app = Flask(__name__)
app.secret_key = "amerta_secret_key"

# Koneksi ke database MySQL
db = mysql.connector.connect(
    host="localhost",
    user="root",  
    password="",  
    database="amerta"
)

cursor = db.cursor(dictionary=True)

# login 
# Fungsi untuk mengecek login dari database
def check_login(username, password):
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()

    if user:
        stored_password = user['password']  # Ambil password hash dari database        
        # Pastikan password dari database bertipe string sebelum digunakan
        if isinstance(stored_password, bytes):
            stored_password = stored_password.decode('utf-8')

        if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
            return user  # Login sukses

    return None  # Login gagal


@app.route('/', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('stok'))  # Jika sudah login, langsung ke stok barang

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = check_login(username, password)
        if user:
            session['username'] = user['username']
            return redirect(url_for('stok'))  # Redirect ke stok barang
        else:
            return render_template('login.html', error="Username atau Password salah!")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# stok page 
@app.route('/stok')
def stok():
    if 'username' not in session:
        return redirect(url_for('login'))  # Cegah akses tanpa login

    cursor.execute("SELECT * FROM barang")  # Ambil data stok dari database
    barang = cursor.fetchall()

    return render_template("stok.html", barang=barang)

@app.route("/add", methods=["POST"])
def add_barang():
    cursor = db.cursor(dictionary=True) 
    kode_barang = request.form["kode_barang"]
    nama_barang = request.form["nama_barang"].lower()
    jumlah = request.form["jumlah"]
    harga = request.form["harga"]
    supplier_baru = request.form["supplier_aktif"].lower()
    tanggal_tambah = datetime.now()
    
    # Periksa apakah nama barang sudah ada
    cursor.execute("SELECT kode_barang, jumlah, supplier_aktif FROM barang WHERE nama_barang=%s", (nama_barang,))
    result = cursor.fetchone()
    
    try :
        if result:
            kode_barang_existing = result["kode_barang"]
            jumlah_sekarang = result["jumlah"]
            supplier_lama = result["supplier_aktif"]
            jumlah_baru = jumlah_sekarang + int(jumlah)

            cursor.execute("UPDATE barang SET jumlah=%s, supplier_aktif=%s WHERE kode_barang=%s", (jumlah_baru, supplier_baru, kode_barang_existing))
            
            # Tambahkan riwayat pengisian stok
            cursor.execute("INSERT INTO riwayat_pengisian_stok (kode_barang, jumlah_ditambahkan, supplier, tanggal) VALUES (%s, %s, %s, %s)",
                           (kode_barang_existing, jumlah, supplier_baru, tanggal_tambah))

        else:
                # Jika barang belum ada, masukkan data baru
                cursor.execute("INSERT INTO barang (kode_barang, nama_barang, jumlah, harga, supplier_aktif) VALUES (%s, %s, %s, %s, %s)", 
                            (kode_barang, nama_barang, jumlah, harga, supplier_baru))
                # Tambahkan riwayat pengisian stok
                cursor.execute("INSERT INTO riwayat_pengisian_stok (kode_barang, jumlah_ditambahkan, supplier, tanggal) VALUES (%s, %s, %s, %s)",
                           (kode_barang, jumlah, supplier_baru, tanggal_tambah))
        
        # Periksa apakah supplier sudah ada di tabel supplier
        cursor.execute("SELECT nama_supplier FROM supplier WHERE nama_supplier = %s", (supplier_baru,))
        supplier_exists = cursor.fetchone()
        
        if not supplier_exists:
            cursor.execute("INSERT INTO supplier (nama_supplier) VALUES (%s)", (supplier_baru,))
        
        # Hapus supplier yang tidak lagi digunakan dalam tabel barang
        cursor.execute("DELETE FROM supplier WHERE nama_supplier NOT IN (SELECT DISTINCT supplier_aktif FROM barang)")

        db.commit()
        flash("Barang berhasil ditambahkan dan diperbarui!", "success")

    except mysql.connector.Error as err:
        db.rollback()  # Rollback jika ada error
        flash(f"Error: {err}", "danger")
    
    return redirect("/")

@app.route("/update", methods=["POST"])
def update_barang():
    cursor = db.cursor(dictionary=True)  
    kode_barang = request.form["kode_barang"].upper()
    nama_barang = request.form["nama_barang"].lower()
    jumlah = request.form["jumlah"]
    harga = request.form["harga"]
    supplier_baru = request.form["supplier_aktif"].lower()
    tanggal_update = datetime.now()
    

    # Ambil data lama sebelum update
    cursor.execute("SELECT jumlah, supplier_aktif FROM barang WHERE kode_barang=%s", (kode_barang,))
    result = cursor.fetchone()

    if not result:
        flash("Barang tidak ditemukan!", "danger")
        return redirect("/")
    
    jumlah_lama = result["jumlah"]
    supplier_lama = result["supplier_aktif"]

    # Periksa apakah nama barang sudah ada untuk barang lain
    cursor.execute("SELECT COUNT(*) AS count FROM barang WHERE nama_barang=%s AND kode_barang!=%s", 
                   (nama_barang, kode_barang))
    result = cursor.fetchone()

    if result["count"] > 0:
        flash("Barang dengan nama yang sama sudah ada!", "danger")
        return redirect("/")

    try:
        # Update barang di tabel `barang`
        cursor.execute("UPDATE barang SET nama_barang=%s, jumlah=%s, harga=%s, supplier_aktif=%s WHERE kode_barang=%s",
                       (nama_barang, jumlah, harga, supplier_baru, kode_barang))

        # Hitung jumlah stok yang ditambahkan
        jumlah_ditambahkan = int(jumlah) - jumlah_lama

        # Jika stok bertambah, simpan ke `riwayat_pengisian_stok`
        if jumlah_ditambahkan > 0:
            cursor.execute("INSERT INTO riwayat_pengisian_stok (kode_barang, jumlah_ditambahkan, supplier, tanggal) VALUES (%s, %s, %s, %s)",
                           (kode_barang, jumlah_ditambahkan, supplier_baru, tanggal_update))
            
        # Periksa apakah supplier sudah ada di tabel supplier
        cursor.execute("SELECT nama_supplier FROM supplier WHERE nama_supplier = %s", (supplier_baru,))
        supplier_exists = cursor.fetchone()
        
        if not supplier_exists:
            cursor.execute("INSERT INTO supplier (nama_supplier) VALUES (%s)", (supplier_baru,))

        # Hapus supplier yang tidak lagi digunakan dalam tabel barang
        cursor.execute("DELETE FROM supplier WHERE nama_supplier NOT IN (SELECT DISTINCT supplier_aktif FROM barang)") 

        db.commit()
        flash("Barang berhasil diupdate!", "success")
    except mysql.connector.Error as err:
        db.rollback()  # Rollback jika terjadi error
        flash(f"Error: {err}", "danger")
    
    return redirect("/")


@app.route("/delete/<kode_barang>")
def delete_barang(kode_barang):
    cursor = db.cursor()
    cursor.execute("DELETE FROM barang WHERE kode_barang=%s", (kode_barang,))

    # Hapus supplier yang tidak lagi digunakan dalam tabel barang
    cursor.execute("DELETE FROM supplier WHERE nama_supplier NOT IN (SELECT DISTINCT supplier_aktif FROM barang)")

    db.commit()
    flash("Barang berhasil dihapus!", "success")
    return redirect("/")


# transaksi page 
@app.route("/transaksi", methods=["GET", "POST"])
def transaksi():
    if request.method == "POST":
        nama_pembeli = request.form["nama_pembeli"]
        total_pembelian = float(request.form["total_pembelian"])
        tanggal_transaksi = datetime.now()

        # Mulai transaksi
        try:
            # Simpan transaksi ke tabel transaksi
            cursor.execute("INSERT INTO transaksi (tanggal, nama_pembeli, total_pembelian) VALUES (%s, %s, %s)",
                           (tanggal_transaksi, nama_pembeli, total_pembelian))
            db.commit()

            # Update stok barang berdasarkan transaksi
            for i in range(0, len(request.form)//4):
                kode_barang = request.form.get(f"kode_barang_{i}")
                jumlah_barang = int(request.form.get(f"jumlah_{i}"))

                # Ambil stok barang saat ini
                cursor.execute("SELECT jumlah FROM barang WHERE kode_barang = %s", (kode_barang,))
                stok_barang = cursor.fetchone()
                if stok_barang and stok_barang["jumlah"] >= jumlah_barang:
                    # Update stok barang setelah transaksi berhasil disimpan
                    cursor.execute("UPDATE barang SET jumlah = jumlah - %s WHERE kode_barang = %s",
                                   (jumlah_barang, kode_barang))
                else:
                    flash(f"Stok barang {kode_barang} tidak mencukupi!", "danger")
                    db.rollback()  # Rollback transaksi jika ada stok yang tidak mencukupi
                    return redirect(url_for("transaksi"))

            db.commit()  # Commit transaksi setelah update stok
            flash("Transaksi berhasil disimpan!", "success")
            return redirect(url_for("transaksi"))
        except Exception as e:
            db.rollback()  # Rollback jika ada error dalam proses transaksi
            flash(f"Terjadi kesalahan: {str(e)}", "danger")
            return redirect(url_for("transaksi"))

    # Ambil data barang untuk dropdown
    cursor.execute("SELECT * FROM barang")
    barang = cursor.fetchall()
    return render_template("transaksi.html", barang=barang, current_time=datetime.now())

# supplier page
@app.route("/supplier")
def supplier_management():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM supplier")
    suppliers = cursor.fetchall()
    cursor.close()
    return render_template("supplier_management.html", suppliers=suppliers)

@app.route("/update_supplier", methods=["POST"])
def update_supplier():
    nama_supplier = request.form["nama_supplier"]
    alamat = request.form.get("alamat")
    nomor_telepon = request.form.get("nomor_telepon")

    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE supplier SET alamat = %s, nomor_telepon = % s WHERE nama_supplier = %s",
            (alamat, nomor_telepon, nama_supplier)
        )
        db.commit()
        flash("Supplier berhasil diperbarui!", "success")
    except mysql.connector.Error as err:
        db.rollback()
        flash(f"Error: {err}", "danger")
    finally:
        cursor.close()
    
    return redirect("/supplier")


# laporan transaksi
@app.route('/laporan/laporan_transaksi', methods=['GET', 'POST'])
def laporan():
    transaksi = []
    filter_type = request.form.get('filter_type', 'harian') # Default filter_type ke 'harian'

    if request.method == 'POST':
        try:
            if filter_type == 'harian':
                tanggal = request.form.get('tanggal')
                if tanggal:
                    query = "SELECT tanggal, nama_pembeli, total_pembelian FROM transaksi WHERE DATE(tanggal) = %s"
                    cursor.execute(query, (tanggal,))
                    transaksi = cursor.fetchall()

            elif filter_type == 'bulanan':
                bulan = request.form.get('bulan')
                tahun = request.form.get('tahun')
                if bulan and tahun:
                    query = """
                        SELECT tanggal, nama_pembeli, total_pembelian 
                        FROM transaksi 
                        WHERE MONTH(tanggal) = %s AND YEAR(tanggal) = %s
                    """
                    cursor.execute(query, (bulan, tahun))
                    transaksi = cursor.fetchall()

        except Exception as e:
            print(f"Error fetching transactions: {e}")

    return render_template('laporan_transaksi.html', transaksi=transaksi)

@app.route('/laporan/download_laporan_transaksi', methods=['POST'])
def download_laporan():
    transaksi = []
    filter_type = request.form.get('filter_type', 'harian')  # Default filter_type ke 'harian'
    filename_suffix = ""

    try:
        # Ambil data dari database berdasarkan filter_type
        if filter_type == 'harian':
            tanggal = request.form.get('tanggal')
            if tanggal:
                query = """
                    SELECT tanggal, nama_pembeli, total_pembelian 
                    FROM transaksi 
                    WHERE DATE(tanggal) = %s
                """
                cursor.execute(query, (tanggal,))
                transaksi = cursor.fetchall()
                filename_suffix = f"_{tanggal}"

        elif filter_type == 'bulanan':
            bulan = request.form.get('bulan')
            tahun = request.form.get('tahun')
            if bulan and tahun:
                query = """
                    SELECT tanggal, nama_pembeli, total_pembelian 
                    FROM transaksi 
                    WHERE MONTH(tanggal) = %s AND YEAR(tanggal) = %s
                """
                cursor.execute(query, (bulan, tahun))
                transaksi = cursor.fetchall()
                nama_bulan = datetime.strptime(bulan, "%m").strftime("%B")
                filename_suffix = f"_{nama_bulan}{tahun}"

        # Cek apakah transaksi ada
        if transaksi:
            # Ubah transaksi menjadi DataFrame
            df = pd.DataFrame(transaksi, columns=['tanggal', 'nama_pembeli', 'total_pembelian'])
            
            # Format kolom tanggal menjadi format yang sesuai (jika diperlukan)
            df['tanggal'] = pd.to_datetime(df['tanggal']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Simpan ke file Excel dalam memory buffer
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Transaksi')
            
            output.seek(0)
            filename = f"Laporan_Transaksi{filename_suffix}.xlsx"
            return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # Jika tidak ada transaksi
        return "Tidak ada data transaksi yang ditemukan.", 404

    except Exception as e:
        print(f"Error fetching transactions: {e}")
        return f"Terjadi kesalahan saat mengambil data transaksi: {e}", 500


# Laporan Riwayat Stok
@app.route('/laporan/laporan_riwayat_stok', methods=['GET', 'POST'])
def laporan_riwayat_stok():
    riwayat_stok = []
    filter_type = request.form.get('filter_type', 'harian') # Default filter_type ke 'harian'

    if request.method == 'POST':
        try:
            if filter_type == 'harian':
                tanggal = request.form.get('tanggal')
                if tanggal:
                    query = """
                        SELECT kode_barang, jumlah_ditambahkan, supplier, tanggal 
                        FROM riwayat_pengisian_stok 
                        WHERE DATE(tanggal) = %s
                    """
                    cursor.execute(query, (tanggal,))
                    riwayat_stok = cursor.fetchall()

            elif filter_type == 'bulanan':
                bulan = request.form.get('bulan')
                tahun = request.form.get('tahun')
                if bulan and tahun:
                    query = """
                        SELECT kode_barang, jumlah_ditambahkan, supplier, tanggal 
                        FROM riwayat_pengisian_stok 
                        WHERE MONTH(tanggal) = %s AND YEAR(tanggal) = %s
                    """
                    cursor.execute(query, (bulan, tahun))
                    riwayat_stok = cursor.fetchall()

        except Exception as e:
            print(f"Error fetching stock history: {e}")

    return render_template('laporan_riwayat_stok.html', riwayat_stok=riwayat_stok)


@app.route('/laporan/download_laporan_riwayat_stok', methods=['POST'])
def download_laporan_stok():
    riwayat_stok = []
    filter_type = request.form.get('filter_type', 'harian')  # Default filter_type ke 'harian'
    filename_suffix = ""

    try:
        # Ambil data dari database berdasarkan filter_type
        if filter_type == 'harian':
            tanggal = request.form.get('tanggal')
            if tanggal:
                print(f"Menjalankan query untuk tanggal: {tanggal}")  # Debugging
                query = """
                    SELECT kode_barang, jumlah_ditambahkan, supplier, tanggal 
                    FROM riwayat_pengisian_stok 
                    WHERE DATE(tanggal) = %s
                """
                cursor.execute(query, (tanggal,))
                riwayat_stok = cursor.fetchall()
                filename_suffix = f"_{tanggal}"

        elif filter_type == 'bulanan':
            bulan = request.form.get('bulan')
            tahun = request.form.get('tahun')
            if bulan and tahun:
                query = """
                    SELECT kode_barang, jumlah_ditambahkan, supplier, tanggal 
                    FROM riwayat_pengisian_stok 
                    WHERE MONTH(tanggal) = %s AND YEAR(tanggal) = %s
                """
                cursor.execute(query, (bulan, tahun))
                riwayat_stok = cursor.fetchall()
                nama_bulan = datetime.strptime(bulan, "%m").strftime("%B")
                filename_suffix = f"_{nama_bulan}{tahun}"

        # Cek apakah riwayat stok ada
        if riwayat_stok:
            # Ubah riwayat stok menjadi DataFrame
            df = pd.DataFrame(riwayat_stok, columns=['kode_barang', 'jumlah_ditambahkan', 'supplier', 'tanggal'])
            
            # Format kolom tanggal menjadi format yang sesuai (jika diperlukan)
            df['tanggal'] = pd.to_datetime(df['tanggal']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Simpan ke file Excel dalam memory buffer
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Riwayat Stok')

            output.seek(0)
            filename = f"Laporan_Stok{filename_suffix}.xlsx"
            return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            return "Tidak ada data yang tersedia", 404

    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
        return "Terjadi kesalahan saat mengunduh laporan", 500

    
if __name__ == "__main__":
    app.run(debug=True)
