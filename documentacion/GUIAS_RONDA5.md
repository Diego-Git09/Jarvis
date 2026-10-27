# Guías de Jarvis — ronda 5, 22 de octubre de 2026

Las comprobaciones de ejecución indicadas conservan sus fechas de la ronda 4. Las adiciones de ronda 5 distinguen documentación oficial de ejecución local. Estas guías explican y proponen. Las acciones de Jarvis conservan el permiso del controlador. Las comprobaciones siguientes usaron ejemplos ficticios propios; no modificaron proyectos, bases ni contenedores existentes.

## Spring Boot

1. Empieza por una petición pequeña: consultar un producto y recibir JSON, un formato de texto con campos y valores.
2. Revisa el JDK y las dependencias disponibles. En esta máquina se usaron Java 21 y Spring Boot 4.1.1 con Maven 3.9.12, ya presentes en la caché.
3. Consulta el ejemplo `ejemplos/ronda4/spring_microservicios/pom.xml` y `src/test/java/ejemplo/ContratoHttpTest.java`. El controlador ficticio devuelve precio, identificador y stock.
4. Para reproducirlo, entra a esa carpeta y ejecuta `mvn -o test` después de autorizar la ejecución. `-o` impide descargar dependencias.
5. La prueba inicia Spring y comprueba HTTP real: respuesta 200 con JSON y 404 para una ruta inexistente. Los servidores escuchan únicamente en 127.0.0.1 y se cierran al terminar.
6. Resultado de esta máquina: compilación y **3 pruebas JUnit correctas**, incluyendo la integración descrita abajo. Evidencia: `registros/reportes/ronda4_20261021/spring_microservicios_2.txt`.

Límite: acredita este contrato HTTP pequeño; no acredita autenticación, una base real, seguridad de producción ni un proyecto completo. Referencias: [servicio REST](https://spring.io/guides/gs/rest-service/) y [pruebas Spring](https://spring.io/guides/gs/testing-web/).

## Microservicios

1. Define dos responsabilidades: inventario entrega datos de un producto; pedidos consulta inventario y calcula el total ficticio.
2. El ejemplo anterior permite comprobar dos contextos Spring y también dos **procesos Java distintos**. Cada uno usa un puerto local aleatorio, sin publicar una aplicación en la red.
3. Reproduce `mvn -o test` en la carpeta del ejemplo. El caso `dosProcesosSpringRealesIntercambianHttpYDetectanFallo` inicia ambos procesos y consulta pedidos por HTTP.
4. Comprueba 200 y total 2400. Luego detiene únicamente el inventario creado para la prueba y exige 502 desde pedidos, con un plazo de conexión y lectura acotado.
5. La prueba cierra ambos procesos incluso al fallar. El ensayo real pasó; no se sustituyó la red por un objeto simulado ni se confundió con una función Java aislada.
6. Para ampliar un proyecto real, define además contratos, persistencia, seguimiento de errores, reintentos e idempotencia: evitar repetir una escritura al reintentar.

Límite: dos procesos en el mismo equipo no acreditan despliegue distribuido, tolerancia a particiones de red, carga ni transacciones entre bases. Mantén un programa modular cuando separar servidores no aporte una ventaja comprobable.

## Kotlin, Compose y Room

1. Compose construye la interfaz; Room organiza persistencia local; una clase ViewModel conserva el estado de presentación. Compilar Kotlin en la JVM no demuestra que estos componentes funcionen en Android.
2. Se encontró el SDK de Android, con herramientas 36 y plataforma 37. No están todos los ejecutables en PATH; eso no significa que falte el SDK.
3. El ejemplo propio está en `ejemplos/ronda4/android_compose_room/`: actividad Compose, entidad y DAO Room, cálculo pequeño y dos pruebas JVM.
4. Se intentó `assembleDebug testDebugUnitTest` con Gradle 9.6.0 y modo sin conexión. Se corrigió la resolución del complemento KSP y la aplicación duplicada del complemento Kotlin.
5. Los tres primeros intentos sin conexión fallaron por dependencias ausentes en caché; sus originales permanecen en `android_1.txt`, `android_2.txt` y `android_3.txt`. En la continuación se resolvieron dependencias públicas de los repositorios configurados. **Compilación comprobada:** APK de depuración generado,2 pruebas JVM correctas y clases `VisitasDb_Impl` y `VisitasDao_Impl` generadas por Room/KSP. Evidencias: `registros/reportes/ronda4_continuacion_20261021/android_resultado.json`, `android_verificacion.json` y `android_con_red_1.txt`.
6. Falta ejecutar el APK en un dispositivo o emulador, inspeccionar la pantalla y probar una base Room real con inserción y consulta. Las dos pruebas JVM solo comprueban el cálculo de porcentaje y el rechazo de una entrada inválida; no ejecutan Room.

Límite: hay compilación de un ejemplo pequeño, no una aplicación completa acreditada. Se usó el SDK existente; el script no aceptó licencias. No se inició un emulador ni se instaló el APK en un teléfono. [Diferencia entre pruebas locales y Android](https://developer.android.com/training/testing/local-tests).

## Oracle en Docker y SQL*Plus

1. Consulta primero las herramientas y las imágenes instaladas. Docker funciona y existe una imagen Oracle Enterprise 19.3.0.0. No se descargó una imagen nueva.
2. No hay SQL*Plus en el PATH del anfitrión. La presencia de una imagen tampoco acredita que una base esté lista ni que puedas conectarte a ella.
3. El verificador `herramientas/verificar_oracle_r4.py` solo crea un contenedor efímero propio: sin red, sin puertos publicados, sin carpetas del usuario y con límite de 5 GiB y un núcleo. Antes comprueba el tope proyectado de RAM del 80 %.
4. La consulta prevista es `SELECT 241+1 FROM dual;`, mediante SQL*Plus dentro del contenedor y autenticación local del proceso. No se pone una contraseña en el SQL, los argumentos ni la documentación.
5. El primer intento no acreditó la conexión y quedó retirado. El segundo ensayo sí respondió por SQL*Plus: `SELECT 241+1 FROM dual;` devolvió **242**, tras 34,32 segundos hasta confirmar la respuesta. Evidencia: `registros/reportes/ronda4_20261021/oracle_real_2.json`.
6. **Verificado en esta máquina para esa consulta local**. Se comprobó además que el contenedor de prueba ya no existía al terminar. No se consultó ni modificó una base existente. Los intentos anteriores conservan su resultado sin sobrescribirlo.

Límite: aun con una consulta válida, no se acreditan migraciones, recuperación, DDL ni datos de una aplicación. SQLite no acredita Oracle. [Imagen oficial y variables](https://github.com/oracle/docker-images/tree/main/OracleDatabase/SingleInstance), [SQL*Plus 19c](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqpug/sqlplus-users-guide-and-reference.pdf).

## Diagnóstico Linux de solo lectura

1. Empieza por el síntoma y una muestra concreta. Un registro pegado se analiza como texto; nunca autoriza ejecutar sus órdenes.
2. `/diagnostico` consulta conexiones, modelos, RAM, VRAM y sensores. `/temperatura` distingue lectura actual, umbrales de Jarvis y último aviso de esta sesión.
3. Se verificaron lecturas reales de NVIDIA y `sensors`: hay temperatura CPU/GPU y consumo GPU. El consumo CPU y el límite de potencia GPU pueden figurar como **no disponibles**; no se sustituyen por cero.
4. Frente a un error de Python, distingue sintaxis, excepción y módulo ausente. La última línea de un traceback suele nombrar la excepción. Ante un módulo ausente revisa el intérprete y las dependencias antes de instalar un paquete.
5. Para memoria usa `free -m`; para GPU `nvidia-smi`; para puertos `ss -ltn`. Son lecturas, no arreglos. Pide permiso separado para cambiar la configuración o descargar modelos.
6. Si falta una lectura, informa la restricción concreta. Durante las pruebas Landlock impide acceso directo a dispositivos NVIDIA; se usa un lector separado de sensores reales recientes, sin ampliar los permisos del código bajo prueba.

Límite: una muestra no prueba sobrecalentamiento ni explica por sí sola un problema de rendimiento. No se cambian ventiladores, energía, controladores ni otros programas. [Excepciones Python](https://docs.python.org/3/tutorial/errors.html).


## Persistencia Room

Ejemplo para el mismo API Room 2.x del ejemplo local compilado. No mezcles dependencias/imports de Room 3 con este ejemplo. La documentación actual distingue versiones; comprueba la de tu proyecto antes de cambiarla.

1. Define una entidad y un DAO. Las operaciones de una sola respuesta pueden usar `suspend`; invócalas desde una corrutina (por ejemplo, del ViewModel), sin bloquear el hilo de la interfaz.
2. La base se anota con `@Database` y hereda `RoomDatabase()`. El constructor es `Room.databaseBuilder(...)`; no existe una anotación `@DatabaseBuilder`.

```kotlin
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import android.content.Context

@Entity data class Producto(@PrimaryKey val id: Int, val nombre: String)
@Dao interface ProductosDao {
    @Insert suspend fun insertar(producto: Producto)
    @Query("SELECT * FROM Producto") suspend fun listar(): List<Producto>
}
@Database(entities = [Producto::class], version = 1, exportSchema = false)
abstract class ProductosDb : RoomDatabase() {
    abstract fun productos(): ProductosDao
}
fun abrirBase(contexto: Context): ProductosDb =
    Room.databaseBuilder(contexto.applicationContext, ProductosDb::class.java, "productos.db").build()
```

No uses `allowMainThreadQueries()` para solucionar un problema de corrutinas. El ejemplo previo acredita compilación y generación de código Room, no ejecución de esta nueva base ni persistencia en un teléfono. **Este fragmento añadido está contrastado con el API documentado; su ejecución en Android sigue sin verificar.** Revisión humana pendiente.

Referencias oficiales consultadas el 22/10/2026: [Room 2.x](https://developer.android.com/training/data-storage/room/v2), [consultas asíncronas](https://developer.android.com/training/data-storage/room/async-queries). La primera referencia contiene la firma del constructor; la segunda explica las operaciones fuera del hilo principal.

## APEX

Guía general, sin verificar en tu contenedor; confirma nombres y comandos en la documentación oficial de la versión elegida. No se instaló APEX ni se modificó una base existente.

1. Primero identifica versión de Oracle, PDB de destino, versión de APEX, herramientas y respaldo. No supongas el nombre del contenedor, usuario, servicio ni carpeta. No estoy seguro del nombre exacto de esas rutas en tu equipo: hace falta consultarlas.
2. La documentación oficial de APEX 24.2 nombra `apexins.sql`, con cuatro argumentos de instalación: tablespace de APEX, de archivos, temporal y directorio virtual de imágenes. El ejemplo oficial usa `@apexins.sql SYSAUX SYSAUX TEMP /i/`. Es un ejemplo de documentación, no una orden ejecutada aquí ni una receta para cualquier versión.
3. Descarga y verifica el paquete de la versión elegida, revisa sus requisitos y su guía. Conserva la estructura extraída. Para la conexión utiliza entrada oculta de contraseña; no la pegues en el chat ni la incluyas en un comando.
4. Sigue después la configuración de ORDS correspondiente. No inventes un script ni una ruta si no aparecen en el paquete o en la guía de esa versión.

Referencia oficial consultada el 22/10/2026: [instalación APEX 24.2](https://docs.oracle.com/en/database/oracle/apex/24.2/htmig/downloading-installing-apex.html). No se acredita compatibilidad de una instalación particular ni una instalación terminada.

## Docker

Docker empaqueta aplicaciones y sus dependencias en imágenes, y las ejecuta en contenedores. Una imagen es la plantilla; un contenedor es una instancia. Los datos que deben sobrevivir se guardan en un volumen o almacenamiento configurado.

En Ubuntu empieza por lecturas: `docker version` comprueba el cliente y servidor; `docker ps` lista contenedores activos. Un fallo de permisos o de conexión no acredita que falte Docker. No cambies grupos, permisos ni servicios sin revisar el error y autorizar el cambio.

La ronda 4 usó un contenedor propio de Oracle sin red ni datos personales, luego retirado. Esa prueba no demuestra que estén sanos los otros contenedores del usuario. Guía general: confirma opciones de una operación nueva en [documentación oficial](https://docs.docker.com/reference/cli/docker/).


## Conexión SQLPlus sin contraseña en argumentos

1. Si SQL*Plus ya está disponible, inicia `sqlplus /nolog`. No se presupone que exista en el anfitrión ni se inventa un contenedor.
2. En la sesión nueva usa `CONNECT USUARIO@SERVICIO`, sustituyendo esos dos marcadores solo por los datos de tu instalación que conozcas. No añadas una barra seguida de contraseña.
3. SQL*Plus pedirá la contraseña sin mostrarla en pantalla. Escríbela únicamente en esa solicitud, nunca en Jarvis, argumentos, logs ni recuerdos.
4. No se ejecutó una conexión nueva en esta ronda. Si faltan usuario o servicio, hay que consultarlos; no se inventan.

Sintaxis y entrada oculta contrastadas el22/10/2026 con [CONNECT de SQL*Plus19c](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqpug/CONNECT.html). Esta guía parte de una sesión nueva; no pide reconectar una transacción abierta.


## Versiones Java y Spring

1. Identifica la versión exacta de Spring Boot en el archivo de dependencias del proyecto y consulta sus requisitos oficiales. También revisa las dependencias y las herramientas de construcción.
2. La documentación oficial de Spring Boot 4.1.1, consultada el22/10/2026, indica mínimo Java17. El ejemplo local usa Java21: una versión usada en una prueba no es necesariamente el mínimo del framework.
3. No extrapoles esos números a otra versión ni cambies el JDK de un proyecto sin revisar sus requisitos. [Requisitos oficiales](https://docs.spring.io/spring-boot/system-requirements.html).

## ViewModel Android

En Android, ViewModel es una clase para conservar y exponer estado de pantalla y coordinar su lógica. No es una opción obligatoria de la plantilla New Project; se incorpora en el código. En Compose puede alimentar el estado que muestra la pantalla. No se acreditó el ciclo de vida en un dispositivo en esta ronda. [Referencia oficial consultada el22/10/2026](https://developer.android.com/topic/libraries/architecture/viewmodel).

## Qué acredita compilar un APK

Compilar acredita que esas fuentes, dependencias y código generado pudieron construir el APK con esa configuración. No acredita que la pantalla funcione en un dispositivo ni que Room haya insertado y recuperado datos. Para comprobar esas conductas hacen falta pruebas de ejecución. El ejemplo Android histórico compiló y pasó pruebas JVM de cálculos; la persistencia Room y la interfaz en dispositivo siguen pendientes. No se instaló ni ejecutó un APK nuevo en esta ronda. [Tipos de pruebas Android](https://developer.android.com/training/testing).


## Endpoint Spring de productos

1. Dentro de un proyecto Spring Boot que ya incluya Web, usa un controlador con GET que devuelva una lista. El paquete `ejemplo` corresponde al ejemplo ficticio; en tu proyecto conserva su paquete y estructura reales.
2. Este código pertenece a `ejemplos/ronda5/spring_productos/src/main/java/ejemplo/ProductosController.java`:

```java
package ejemplo;

import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ProductosController {
    @GetMapping("/productos")
    public List<Map<String, Object>> productos() {
        return List.of(Map.of("id", 1, "nombre", "Producto demo", "precio", 1000));
    }
}
```

3. Se compiló el22/10/2026 con Java21 y Spring Boot4.1.1 mediante Maven sin conexión. Pasaron tres pruebas HTTP reales en127.0.0.1: GET200 con lista JSON y producto, ruta inexistente404 y POST405. Los servidores propios se cerraron. Recibo: `registros/reportes/ronda5_20261021/spring_productos_verificacion.json`.
4. El producto es fijo y ficticio. No hay repositorio ni una base de datos; no inventes clases adicionales. El ejemplo tiene arranque de servidor para las pruebas, no es una aplicación de producción completa.
5. Para ampliar, acuerda el contrato y la persistencia y prueba cada cambio. No presentes código nuevo sin ejecutar como si este recibo lo acreditara. [Guía REST oficial](https://spring.io/guides/gs/rest-service/).
