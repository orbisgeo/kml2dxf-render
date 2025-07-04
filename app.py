from flask import Flask, render_template, request, send_file, flash
import geopandas as gpd
import ezdxf
from ezdxf import units
import os
import io # Para manipular arquivos em memória

app = Flask(__name__)
app.secret_key = 'uma_chave_secreta_e_aleatoria_para_flash_messages' # Necessário para usar flash messages

# ---------- FUNÇÕES PRINCIPAIS (Reaproveitadas do seu código original) ----------
def reprojetar_para_epsg(gdf, epsg):
    """Reprojeta um GeoDataFrame para um novo sistema de coordenadas EPSG."""
    try:
        return gdf.to_crs(epsg=epsg)
    except Exception as e:
        raise ValueError(f"Erro ao reprojetar para EPSG {epsg}: {e}")

def geometria_para_dxf(geom, msp):
    """Converte uma geometria shapely para entidades DXF no modelspace."""
    if geom.geom_type == "Point":
        msp.add_point((geom.x, geom.y))
    elif geom.geom_type == "LineString":
        msp.add_lwpolyline(list(geom.coords))
    elif geom.geom_type == "Polygon":
        msp.add_lwpolyline(list(geom.exterior.coords), close=True)
        for interior in geom.interiors:
            msp.add_lwpolyline(list(interior.coords), close=True)
    elif geom.geom_type.startswith("Multi"):
        for part in geom.geoms:
            geometria_para_dxf(part, msp)
    else:
        # Lidar com geometrias desconhecidas ou não suportadas
        print(f"Aviso: Tipo de geometria não suportado/ignorado: {geom.geom_type}")


# ---------- ROTAS FLASK ----------

@app.route('/', methods=['GET'])
def index():
    """Renderiza a página inicial com o formulário de upload."""
    return render_template('index.html')

@app.route('/converter', methods=['POST'])
def converter():
    """Recebe o arquivo KML e o código EPSG, realiza a conversão e envia o DXF."""
    if 'kml_file' not in request.files:
        flash('Nenhum arquivo KML selecionado!', 'error')
        return render_template('index.html')

    kml_file = request.files['kml_file']
    epsg_texto = request.form.get('epsg_code', '').strip()

    if kml_file.filename == '':
        flash('Nenhum arquivo selecionado!', 'error')
        return render_template('index.html')

    if not epsg_texto.isdigit():
        flash('Código EPSG inválido. Por favor, insira um número.', 'error')
        return render_template('index.html')

    epsg = int(epsg_texto)

    try:
        # Ler o KML diretamente da memória
        # geopandas.read_file pode ler de um "file-like object"
        gdf = gpd.read_file(io.BytesIO(kml_file.read()), driver="KML")

        # Reprojetar
        gdf_proj = reprojetar_para_epsg(gdf, epsg)

        # Criar o documento DXF em memória
        doc = ezdxf.new(setup=True)
        doc.units = units.M
        doc.header["$INSUNITS"] = units.M
        msp = doc.modelspace()

        for geom in gdf_proj.geometry:
            geometria_para_dxf(geom, msp)

        # Salvar o DXF em um buffer de memória
        dxf_buffer = io.BytesIO()
        doc.saveas(dxf_buffer)
        dxf_buffer.seek(0) # Volta ao início do buffer para leitura

        # Obter o nome original do arquivo KML para usar no nome do DXF
        original_filename_base = os.path.splitext(kml_file.filename)[0]
        dxf_filename = f"{original_filename_base}_convertido.dxf"

        flash('Conversão concluída com sucesso!', 'success')
        return send_file(
            dxf_buffer,
            mimetype='application/dxf',
            as_attachment=True,
            download_name=dxf_filename
        )

    except ValueError as ve:
        flash(f"Erro de dados: {ve}", 'error')
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'error')

    return render_template('index.html')

if __name__ == '__main__':
    # Usar debug=True apenas para desenvolvimento local
    app.run(debug=True)