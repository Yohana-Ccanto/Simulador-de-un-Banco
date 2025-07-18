import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
import re
import sqlite3 # Importamos la librería para SQLite

# Lógica de negocio con POO
class Cuenta:
    def __init__(self, numero, titular, saldo_inicial):
        self.numero = numero
        self.titular = titular
        self._saldo = saldo_inicial  # Saldo encapsulado
        self.historial = []  # Historial almacenado en memoria (lista de tuplas)
        # Formato de historial: (fecha, tipo, monto)

    def depositar(self, monto):
        if monto <= 0:
            raise ValueError("El monto a depositar debe ser un valor positivo. ¡Inténtalo de nuevo!")
        self._saldo += monto
        self._registrar_transaccion("Depósito", f"+S/. {monto:.2f}")

    def retirar(self, monto):
        if monto <= 0:
            raise ValueError("El monto a retirar debe ser un valor positivo. ¡Verifica el valor ingresado!")
        if monto > self._saldo:
            raise ValueError(f"¡Saldo insuficiente! Tu saldo actual es S/. {self._saldo:.2f}. No puedes retirar S/. {monto:.2f}.")
        self._saldo -= monto
        self._registrar_transaccion("Retiro", f"-S/. {monto:.2f}")

    def transferir(self, destino, monto):
        # Primero retira de la cuenta de origen (aprovecha la validación de retiro)
        self.retirar(monto)
        # Luego deposita en la cuenta de destino (aprovecha la validación de depósito)
        destino.depositar(monto)
        self._registrar_transaccion(f"Transferencia a {destino.numero}", f"-S/. {monto:.2f}")
        destino._registrar_transaccion(f"Transferencia de {self.numero}", f"+S/. {monto:.2f}")

    def _registrar_transaccion(self, tipo, monto_str):
        """Registra la transacción en el historial de la cuenta (en memoria)."""
        fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.historial.append((fecha, tipo, monto_str))
        # Aquí se necesita una forma de notificar a la base de datos
        # Esto lo manejaremos desde BancaApp después de cada operación

    def aplicar_interes(self):
        """Método polimórfico para aplicar interés, a ser implementado por subclases."""
        pass

    def saldo(self):
        """Devuelve el saldo actual de la cuenta."""
        return self._saldo

class CuentaAhorro(Cuenta):
    def aplicar_interes(self):
        tasa_anual = 0.01  # 1% anual
        tasa_mensual = tasa_anual / 12
        interes_ganado = self._saldo * tasa_mensual
        self._saldo += interes_ganado
        self._registrar_transaccion("Interés (Ahorro)", f"+S/. {interes_ganado:.2f}")

class CuentaCorriente(Cuenta):
    def aplicar_interes(self):
        tasa_anual = 0.0005  # 0.05% anual
        tasa_mensual = tasa_anual / 12
        interes_ganado = self._saldo * tasa_mensual
        self._saldo += interes_ganado
        self._registrar_transaccion("Interés (Corriente)", f"+S/. {interes_ganado:.2f}")


# Diccionario global para almacenar los objetos de cuenta en memoria
cuentas = {}

# Interfaz Gráfica (Tkinter)
class BancaApp:
    def __init__(self, master):
        self.master = master
        master.title("Simulador de un Banco Digital")
        master.geometry("500x650")
        master.resizable(False, False)
        master.configure(bg="#e6f2ff")
        self.fuente_normal = ("Helvetica Neue", 10)
        self.fuente_titulo = ("Helvetica Neue", 13, "bold")

        # Conectar a la base de datos y crear tablas si no existen
        self.db_conn = None
        self.init_db()
        # Cargar las cuentas existentes desde la base de datos al iniciar
        self.load_accounts_from_db()

        # Comandos de validación
        self.vcmd_numero = master.register(lambda P: P.isdigit() and len(P) <= 10 or P == "")
        self.vcmd_titular = master.register(lambda P: re.fullmatch(r"[A-Za-zÁÉÍÓÚñáéíóú ]*", P) is not None)
        self.vcmd_saldo = master.register(lambda P: re.fullmatch(r'\d*\.?\d{0,2}', P) is not None)

        self.create_widgets()
    
    def init_db(self):
        """Inicializa la conexión a la base de datos y crea las tablas si no existen."""
        try:
            self.db_conn = sqlite3.connect('banco.db')
            cursor = self.db_conn.cursor()
            
            # Tabla de cuentas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cuentas (
                    numero TEXT PRIMARY KEY,
                    titular TEXT NOT NULL,
                    saldo REAL NOT NULL,
                    tipo TEXT NOT NULL
                )
            ''')
            
            # Tabla de historial de transacciones (con clave foránea a cuentas)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historial (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero_cuenta TEXT NOT NULL,
                    fecha TEXT NOT NULL,
                    tipo_transaccion TEXT NOT NULL,
                    monto_str TEXT NOT NULL,
                    FOREIGN KEY (numero_cuenta) REFERENCES cuentas(numero)
                )
            ''')
            
            self.db_conn.commit()
        except sqlite3.Error as e:
            messagebox.showerror("Error de Base de Datos", f"No se pudo conectar o inicializar la base de datos: {e}")
            self.master.destroy() # Cierra la aplicación si hay un problema con la DB

    def load_accounts_from_db(self):
        """Carga las cuentas y sus historiales desde la base de datos al diccionario global."""
        if not self.db_conn: return # No intentar si la conexión falló

        cursor = self.db_conn.cursor()
        cursor.execute("SELECT numero, titular, saldo, tipo FROM cuentas")
        
        for row in cursor.fetchall():
            numero, titular, saldo, tipo = row
            if tipo == "Ahorro":
                cuenta = CuentaAhorro(numero, titular, saldo)
            elif tipo == "Corriente":
                cuenta = CuentaCorriente(numero, titular, saldo)
            cuentas[numero] = cuenta
            
            # Cargar historial para cada cuenta
            hist_cursor = self.db_conn.cursor()
            hist_cursor.execute("SELECT fecha, tipo_transaccion, monto_str FROM historial WHERE numero_cuenta = ?", (numero,))
            for h_row in hist_cursor.fetchall():
                cuenta.historial.append(h_row) # Asumiendo que el formato de tupla es el mismo

    def update_account_in_db(self, cuenta):
        """Actualiza el saldo y el historial de una cuenta en la base de datos."""
        if not self.db_conn: return

        cursor = self.db_conn.cursor()
        
        # Actualizar saldo
        cursor.execute("UPDATE cuentas SET saldo = ? WHERE numero = ?", (cuenta.saldo(), cuenta.numero))
        
        # Insertar nuevas transacciones en el historial (solo las que aún no están en la DB)
        # Esto requiere un seguimiento de qué transacciones ya se guardaron o vaciar y reinsertar
        # Para simplificar en este ejemplo, reinsertaremos el historial completo para la cuenta
        # En una aplicación real, usarías un ID único para cada transacción y solo insertarías nuevas
        
        cursor.execute("DELETE FROM historial WHERE numero_cuenta = ?", (cuenta.numero,))
        for fecha, tipo, monto_str in cuenta.historial:
            cursor.execute("INSERT INTO historial (numero_cuenta, fecha, tipo_transaccion, monto_str) VALUES (?, ?, ?, ?)",
                           (cuenta.numero, fecha, tipo, monto_str))
        
        self.db_conn.commit()

    def add_new_account_to_db(self, cuenta):
        """Inserta una nueva cuenta en la base de datos."""
        if not self.db_conn: return

        cursor = self.db_conn.cursor()
        cursor.execute("INSERT INTO cuentas (numero, titular, saldo, tipo) VALUES (?, ?, ?, ?)",
                       (cuenta.numero, cuenta.titular, cuenta.saldo(), "Ahorro" if isinstance(cuenta, CuentaAhorro) else "Corriente"))
        self.db_conn.commit()

    def limpiar_entradas(self, *entradas):
        for e in entradas:
            e.delete(0, tk.END)

    def show_frame(self, frame_to_show):
        self.main_frame.pack_forget()
        self.create_account_frame.pack_forget()
        self.operations_frame.pack_forget()
        self.history_frame.pack_forget()
        
        frame_to_show.pack(fill="both", expand=True, padx=20, pady=20)
        if frame_to_show == self.operations_frame:
            self.reset_operation_fields()
        if frame_to_show == self.history_frame:
            self.limpiar_entradas(self.entry_historial)
            for row in self.tree_historial.get_children():
                self.tree_historial.delete(row)

    def create_widgets(self):
        self.main_frame = tk.Frame(self.master, bg="#e6f2ff", padx=20, pady=20)
        
        tk.Label(self.main_frame, text="¿Qué deseas hacer?", font=self.fuente_titulo, bg="#e6f2ff").pack(pady=20)
        
        tk.Button(self.main_frame, text="Abrir Nueva Cuenta", font=("Helvetica Neue", 12, "bold"), 
                  command=lambda: self.show_frame(self.create_account_frame),
                  bg="#4CAF50", fg="white", activebackground="#45a049", padx=20, pady=10, bd=0, relief="raised").pack(pady=10, fill="x")
        
        tk.Button(self.main_frame, text="Realizar Operación", font=("Helvetica Neue", 12, "bold"), 
                  command=lambda: self.show_frame(self.operations_frame),
                  bg="#2196F3", fg="white", activebackground="#1e88e5", padx=20, pady=10, bd=0, relief="raised").pack(pady=10, fill="x")
        
        tk.Button(self.main_frame, text="Ver Historial", font=("Helvetica Neue", 12, "bold"), 
                  command=lambda: self.show_frame(self.history_frame),
                  bg="#673AB7", fg="white", activebackground="#5e35b1", padx=20, pady=10, bd=0, relief="raised").pack(pady=10, fill="x")

        self.main_frame.pack(fill="both", expand=True)

        self.create_account_frame = tk.LabelFrame(self.master, text=" Abrir Nueva Cuenta ", font=self.fuente_titulo, bg="#f0faff", fg="#333333", padx=15, pady=10)
        self.operations_frame = tk.LabelFrame(self.master, text=" Realizar Operación ", font=self.fuente_titulo, bg="#f0faff", fg="#333333", padx=15, pady=10)
        self.history_frame = tk.LabelFrame(self.master, text=" Historial de Transacciones ", font=self.fuente_titulo, bg="#f0faff", fg="#333333", padx=15, pady=10)

        self.setup_create_account_frame()
        self.setup_operations_frame()
        self.setup_history_frame()

    def setup_create_account_frame(self):
        tk.Label(self.create_account_frame, text="Número de Cuenta (10 dígitos)", bg="#f0faff", font=self.fuente_normal).pack(pady=(5, 2))
        self.entry_numero_crear = tk.Entry(self.create_account_frame, font=self.fuente_normal, validate="key", validatecommand=(self.vcmd_numero, '%P'), width=35)
        self.entry_numero_crear.pack(pady=(0, 5))

        tk.Label(self.create_account_frame, text="Titular (Nombre y Apellido)", bg="#f0faff", font=self.fuente_normal).pack(pady=(5, 2))
        self.entry_titular_crear = tk.Entry(self.create_account_frame, font=self.fuente_normal, validate="key", validatecommand=(self.vcmd_titular, '%P'), width=35)
        self.entry_titular_crear.pack(pady=(0, 5))

        tk.Label(self.create_account_frame, text="Saldo Inicial (S/.)", bg="#f0faff", font=self.fuente_normal).pack(pady=(5, 2))
        self.entry_saldo_crear = tk.Entry(self.create_account_frame, font=self.fuente_normal, validate="key", validatecommand=(self.vcmd_saldo, '%P'), width=35)
        self.entry_saldo_crear.pack(pady=(0, 5))

        tk.Label(self.create_account_frame, text="Tipo de Cuenta", bg="#f0faff", font=self.fuente_normal).pack(pady=(5, 2))
        self.tipo_cuenta = tk.StringVar(value="Ahorro")
        ttk.OptionMenu(self.create_account_frame, self.tipo_cuenta, "Ahorro", "Corriente").pack(pady=(0, 10))
        
        tk.Button(self.create_account_frame, text="Crear Cuenta", font=("Helvetica Neue", 11, "bold"), command=self._crear_cuenta,
                  bg="#4CAF50", fg="white", activebackground="#45a049", padx=10, pady=5, bd=0, relief="raised").pack(pady=5)
        
        tk.Button(self.create_account_frame, text="Volver al Inicio", font=self.fuente_normal, command=lambda: self.show_frame(self.main_frame),
                  bg="#ff6666", fg="white", activebackground="#e05252", padx=10, pady=5, bd=0, relief="raised").pack(pady=5)

    def setup_operations_frame(self):
        tk.Label(self.operations_frame, text="Selecciona la Operación", bg="#f0faff", font=self.fuente_normal).pack(pady=(5, 2))
        self.op_type_var = tk.StringVar(value="Depósito")
        self.op_dropdown = ttk.OptionMenu(self.operations_frame, self.op_type_var, "Depósito", "Depósito", "Retiro", "Transferencia", "Aplicar Interés", command=self.update_operation_fields)
        self.op_dropdown.pack(pady=(0, 10))

        tk.Label(self.operations_frame, text="Número de Cuenta", bg="#f0faff", font=self.fuente_normal).pack(pady=(5, 2))
        self.entry_numero_op = tk.Entry(self.operations_frame, font=self.fuente_normal, validate="key", validatecommand=(self.vcmd_numero, '%P'), width=35)
        self.entry_numero_op.pack(pady=(0, 5))
        self.entry_numero_op.bind("<KeyRelease>", self.actualizar_saldo_op)
        self.entry_numero_op.bind("<FocusOut>", self.actualizar_saldo_op)

        self.label_saldo_op = tk.Label(self.operations_frame, text="Saldo actual: ---", bg="#f0faff", font=("Helvetica Neue", 10, "bold"), fg="#333333")
        self.label_saldo_op.pack(pady=(0, 10))

        self.label_monto_op = tk.Label(self.operations_frame, text="Monto (S/.)", bg="#f0faff", font=self.fuente_normal)
        self.entry_monto_op = tk.Entry(self.operations_frame, font=self.fuente_normal, validate="key", validatecommand=(self.vcmd_saldo, '%P'), width=35)
        
        self.label_destino_op = tk.Label(self.operations_frame, text="Cuenta Destino", bg="#f0faff", font=self.fuente_normal)
        self.entry_destino_op = tk.Entry(self.operations_frame, font=self.fuente_normal, validate="key", validatecommand=(self.vcmd_numero, '%P'), width=35)
        
        self.update_operation_fields()

        tk.Button(self.operations_frame, text="Ejecutar", font=("Helvetica Neue", 11, "bold"), command=self._realizar_operacion,
                  bg="#2196F3", fg="white", activebackground="#1e88e5", padx=10, pady=5, bd=0, relief="raised").pack(pady=5)
        
        tk.Button(self.operations_frame, text="Volver al Inicio", font=self.fuente_normal, command=lambda: self.show_frame(self.main_frame),
                  bg="#ff6666", fg="white", activebackground="#e05252", padx=10, pady=5, bd=0, relief="raised").pack(pady=5)

    def setup_history_frame(self):
        tk.Label(self.history_frame, text="Número de Cuenta", bg="#f0faff", font=self.fuente_normal).pack(pady=(5, 2))
        self.entry_historial = tk.Entry(self.history_frame, font=self.fuente_normal, validate="key", validatecommand=(self.vcmd_numero, '%P'), width=35)
        self.entry_historial.pack(pady=(0, 5))
        
        tk.Button(self.history_frame, text="Ver Historial", font=("Helvetica Neue", 11, "bold"), command=self._ver_historial,
                  bg="#673AB7", fg="white", activebackground="#5e35b1", padx=10, pady=5, bd=0, relief="raised").pack(pady=5)

        self.tree_historial = ttk.Treeview(self.history_frame, columns=("Fecha", "Tipo", "Monto"), show="headings", height=8)
        self.tree_historial.heading("Fecha", text="Fecha y Hora")
        self.tree_historial.heading("Tipo", text="Tipo de Transacción")
        self.tree_historial.heading("Monto", text="Monto")
        self.tree_historial.column("Fecha", width=150, anchor="center")
        self.tree_historial.column("Tipo", width=150, anchor="center")
        self.tree_historial.column("Monto", width=100, anchor="center")
        self.tree_historial.pack(expand=True, fill="both", padx=5, pady=5)
        
        tk.Button(self.history_frame, text="Volver al Inicio", font=self.fuente_normal, command=lambda: self.show_frame(self.main_frame),
                  bg="#ff6666", fg="white", activebackground="#e05252", padx=10, pady=5, bd=0, relief="raised").pack(pady=5)

    def update_operation_fields(self, *args):
        self.label_monto_op.pack_forget()
        self.entry_monto_op.pack_forget()
        self.label_destino_op.pack_forget()
        self.entry_destino_op.pack_forget()

        selected_op = self.op_type_var.get()
        
        if selected_op in ["Depósito", "Retiro"]:
            self.label_monto_op.config(text=f"Monto a {selected_op} (S/.)")
            self.label_monto_op.pack(pady=(5, 2))
            self.entry_monto_op.pack(pady=(0, 10))
        elif selected_op == "Transferencia":
            self.label_destino_op.pack(pady=(5, 2))
            self.entry_destino_op.pack(pady=(0, 5))
            self.label_monto_op.config(text="Monto a Transferir (S/.)")
            self.label_monto_op.pack(pady=(5, 2))
            self.entry_monto_op.pack(pady=(0, 10))
        elif selected_op == "Aplicar Interés":
            self.label_monto_op.config(text="Monto de Interés (se calcula)")
            # No se necesita el entry_monto_op para esta operación, solo el número de cuenta.
            # Se podría ocultar completamente o cambiar su estado a "disabled" si fuera necesario.

        self.actualizar_saldo_op()

    def reset_operation_fields(self):
        self.op_type_var.set("Depósito")
        self.limpiar_entradas(self.entry_numero_op, self.entry_monto_op, self.entry_destino_op)
        self.label_saldo_op.config(text="Saldo actual: ---")
        self.update_operation_fields()

    def _crear_cuenta(self):
        try:
            numero = self.entry_numero_crear.get().strip()
            titular = self.entry_titular_crear.get().strip()
            saldo_str = self.entry_saldo_crear.get().strip()
            tipo = self.tipo_cuenta.get()

            if not numero:
                raise ValueError("Por favor, ingresa el (número de cuenta).")
            if not titular:
                raise ValueError("Por favor, ingresa el (nombre y apellido del titular).")
            if not saldo_str:
                raise ValueError("Por favor, ingresa el (saldo inicial).")
            
            saldo = float(saldo_str)

            if not re.match(r"^\d{10}$", numero):
                raise ValueError("El número de cuenta debe tener exactamente (10 dígitos numéricos).")
            if not re.match(r"^[A-Za-zÁÉÍÓÚñáéíóú]+( [A-Za-zÁÉÍÓÚñáéíóú]+)+$", titular):
                raise ValueError("Por favor, ingresa un (nombre y al menos un apellido válidos).")
            if saldo < 0:
                raise ValueError("El saldo inicial no puede ser negativo.")
            if numero in cuentas:
                raise ValueError("¡Ups! Esta cuenta ya existe. Por favor, verifica el número.")

            cuenta = CuentaAhorro(numero, titular, saldo) if tipo == "Ahorro" else CuentaCorriente(numero, titular, saldo)
            cuentas[numero] = cuenta
            
            # ¡NUEVO! Guardar la nueva cuenta en la base de datos
            self.add_new_account_to_db(cuenta)

            messagebox.showinfo("¡Éxito!", "¡Felicidades! La cuenta ha sido creada correctamente.")
            self.limpiar_entradas(self.entry_numero_crear, self.entry_titular_crear, self.entry_saldo_crear)
        except ValueError as ve:
            messagebox.showerror("Error al Crear Cuenta", str(ve))
        except Exception as e:
            messagebox.showerror("Error Inesperado", f"Ocurrió un error inesperado: {e}.")

    def _realizar_operacion(self):
        tipo_operacion = self.op_type_var.get()
        numero = self.entry_numero_op.get().strip()
        monto_str = self.entry_monto_op.get().strip()
        destino = self.entry_destino_op.get().strip()

        try:
            if not numero:
                raise ValueError("Por favor, ingresa el número de cuenta.")
            if numero not in cuentas:
                raise ValueError("La cuenta no fue encontrada.")

            cuenta_origen = cuentas[numero]

            if tipo_operacion == "Depósito":
                if not monto_str: raise ValueError("Ingresa el monto a depositar.")
                monto = float(monto_str)
                cuenta_origen.depositar(monto)
                # ¡NUEVO! Actualizar la cuenta en la base de datos
                self.update_account_in_db(cuenta_origen)
                messagebox.showinfo("Depósito Exitoso", f"¡Depósito realizado! Saldo actual: S/. {cuenta_origen.saldo():.2f}")
            elif tipo_operacion == "Retiro":
                if not monto_str: raise ValueError("Ingresa el monto a retirar.")
                monto = float(monto_str)
                cuenta_origen.retirar(monto)
                # ¡NUEVO! Actualizar la cuenta en la base de datos
                self.update_account_in_db(cuenta_origen)
                messagebox.showinfo("Retiro Exitoso", f"¡Retiro realizado! Saldo restante: S/. {cuenta_origen.saldo():.2f}")
            elif tipo_operacion == "Transferencia":
                if not destino: raise ValueError("Ingresa la cuenta de destino.")
                if not monto_str: raise ValueError("Ingresa el monto a transferir.")
                monto = float(monto_str)
                if destino not in cuentas: raise ValueError("La cuenta de destino no fue encontrada.")
                if numero == destino: raise ValueError("No puedes transferir dinero a la misma cuenta.")
                
                cuenta_destino = cuentas[destino]
                cuenta_origen.transferir(cuenta_destino, monto)
                # ¡NUEVO! Actualizar ambas cuentas en la base de datos
                self.update_account_in_db(cuenta_origen)
                self.update_account_in_db(cuenta_destino)
                messagebox.showinfo("Transferencia Exitosa", f"¡Transferencia realizada con éxito!\nSaldo origen: S/. {cuenta_origen.saldo():.2f}")
            elif tipo_operacion == "Aplicar Interés":
                cuenta_origen.aplicar_interes()
                # ¡NUEVO! Actualizar la cuenta en la base de datos
                self.update_account_in_db(cuenta_origen)
                messagebox.showinfo("Interés Aplicado", f"Interés aplicado correctamente.\nNuevo saldo: S/. {cuenta_origen.saldo():.2f}")
            
            self.limpiar_entradas(self.entry_numero_op, self.entry_monto_op, self.entry_destino_op)
            self.actualizar_saldo_op()

        except ValueError as ve:
            messagebox.showerror(f"Error en {tipo_operacion}", str(ve))
        except Exception as e:
            messagebox.showerror("Error Inesperado", f"Ocurrió un error inesperado: {e}.")

    def _ver_historial(self):
        numero = self.entry_historial.get().strip()
        for row in self.tree_historial.get_children():
            self.tree_historial.delete(row)
        
        if not numero:
            messagebox.showerror("Error", "Por favor, ingresa el número de cuenta para ver su historial.")
            return

        if numero not in cuentas:
            messagebox.showerror("Error", "El número de cuenta no fue encontrado.")
            return

        transacciones = cuentas[numero].historial
        
        if not transacciones:
            messagebox.showinfo("Historial Vacío", "No se encontraron transacciones para esta cuenta.")
        else:
            for fila in transacciones:
                self.tree_historial.insert('', 'end', values=fila)

    def actualizar_saldo_op(self, event=None):
        numero = self.entry_numero_op.get().strip()
        if numero in cuentas:
            self.label_saldo_op.config(text=f"Saldo actual: S/. {cuentas[numero].saldo():.2f}")
        else:
            self.label_saldo_op.config(text="Saldo actual: ---")

# Iniciar la aplicación
root = tk.Tk()
app = BancaApp(root)
root.mainloop()
# Asegurarse de cerrar la conexión a la base de datos al salir
if app.db_conn:
    app.db_conn.close()