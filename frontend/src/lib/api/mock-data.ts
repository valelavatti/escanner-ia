import type { Deposito, Estante, Ubicacion, ProductSearchResult } from './client';

// ---------------------------------------------------------------------------
// Mock data for frontend-only development mode (token === 'dev-token')
// ---------------------------------------------------------------------------

export const MOCK_PRODUCTOS: ProductSearchResult[] = [
	{ sku: 'SKU-001', descripcion: 'Tornillo M6 x 20mm', codigo_de_barra: '7790001000010' },
	{ sku: 'SKU-002', descripcion: 'Tuerca hexagonal M6', codigo_de_barra: '7790001000020' },
	{ sku: 'SKU-003', descripcion: 'Arandela plana 6mm', codigo_de_barra: '7790001000030' },
	{ sku: 'SKU-004', descripcion: 'Perno Allen M8 x 30mm', codigo_de_barra: '7790001000040' },
	{ sku: 'SKU-005', descripcion: 'Remache pop 4mm', codigo_de_barra: '7790001000050' },
	{ sku: 'SKU-006', descripcion: 'Cinta adhesiva doble faz', codigo_de_barra: '7790001000060' },
	{ sku: 'SKU-007', descripcion: 'Llave de tubo 13mm', codigo_de_barra: '7790001000070' },
	{ sku: 'SKU-008', descripcion: 'Pinza de punta fina', codigo_de_barra: '7790001000080' },
];

export const MOCK_DEPOSITOS: Deposito[] = [
	{ id: 1, nombre: 'Depósito Central', estantes_count: 3, usuarios_count: 1 },
	{ id: 2, nombre: 'Depósito Norte', estantes_count: 2, usuarios_count: 1 }
];

function makeUbicaciones(
	estanteId: number,
	estanteNombre: string,
	filas: number,
	columnas: number,
	filaOrder: string,
	columnaOrder: string
): Ubicacion[] {
	const ubicaciones: Ubicacion[] = [];
	const isSuelto = estanteNombre.toLowerCase().startsWith('suelto');

	const filaLabels =
		filaOrder === 'alpha'
			? 'ABCDEFGHIJ'.split('')
			: Array.from({ length: filas }, (_, i) => String(i + 1));
	const colLabels =
		columnaOrder === 'alpha'
			? 'ABCDEFGHIJ'.split('')
			: Array.from({ length: columnas }, (_, i) => String(i + 1));

	// Sample products for demo variety
	const sampleProducts: Array<{ sku: string; descripcion: string; stock: number }> = [
		{ sku: 'SKU-001', descripcion: 'Tornillo M6 x 20mm', stock: 250 },
		{ sku: 'SKU-002', descripcion: 'Tuerca hexagonal M6', stock: 180 },
		{ sku: 'SKU-003', descripcion: 'Arandela plana 6mm', stock: 5 },
		{ sku: 'SKU-004', descripcion: 'Perno Allen M8 x 30mm', stock: 120 },
		{ sku: 'SKU-005', descripcion: 'Remache pop 4mm', stock: 8 },
	];

	let cellIndex = 0;
	for (let f = 1; f <= filas; f++) {
		for (let c = 1; c <= columnas; c++) {
			const filaLabel = filaLabels[f - 1] ?? String(f);
			const colLabel = colLabels[c - 1] ?? String(c);
			const qr = `${estanteNombre}-${filaLabel}${colLabel}`;

			// Assign some mock products deterministically
			let producto_sku: string | null = null;
			let producto_id: string | null = null;
			let producto_descripcion: string | null = null;
			let stock_actual = 0;
			let estado = 'vacio';

			if (!isSuelto && cellIndex % 3 === 0 && cellIndex < sampleProducts.length * 3) {
				const p = sampleProducts[Math.floor(cellIndex / 3) % sampleProducts.length];
				producto_sku = p.sku;
				producto_id = p.sku;
				producto_descripcion = p.descripcion;
				stock_actual = p.stock;
				estado = stock_actual < 10 ? 'bajo' : 'ocupado';
			}

			ubicaciones.push({
				id: estanteId * 1000 + cellIndex,
				estante_id: estanteId,
				estante_nombre: estanteNombre,
				fila: f,
				columna: c,
				fila_label: filaLabel,
				columna_label: colLabel,
				producto_id,
				producto_sku,
				producto_descripcion,
				stock_actual,
				qr_valor: qr,
				estado
			});

			cellIndex++;
		}
	}

	return ubicaciones;
}

const estante1Ubs = makeUbicaciones(1, 'Estante A', 4, 5, 'alpha', 'numeric');
const estante2Ubs = makeUbicaciones(2, 'Estante B', 3, 4, 'alpha', 'numeric');
const estante3Ubs = makeUbicaciones(3, 'Suelto', 2, 3, 'numeric', 'numeric');
const estante4Ubs = makeUbicaciones(4, 'Estante C', 5, 6, 'alpha', 'numeric');
const estante5Ubs = makeUbicaciones(5, 'Estante D', 3, 3, 'alpha', 'numeric');

export const MOCK_ESTANTES: (Estante & { ubicaciones: Ubicacion[] })[] = [
	{
		id: 1,
		nombre: 'Estante A',
		orden_visual: 1,
		filas: 4,
		columnas: 5,
		deposito_id: 1,
		deposito_nombre: 'Depósito Central',
		deleted_at: null,
		created_at: '2024-01-01T00:00:00Z',
		ubicaciones_count: estante1Ubs.length,
		fila_order: 'alpha',
		columna_order: 'numeric',
		fila_format: 'alpha',
		columna_format: 'numeric',
		ubicaciones: estante1Ubs
	},
	{
		id: 2,
		nombre: 'Estante B',
		orden_visual: 2,
		filas: 3,
		columnas: 4,
		deposito_id: 1,
		deposito_nombre: 'Depósito Central',
		deleted_at: null,
		created_at: '2024-01-01T00:00:00Z',
		ubicaciones_count: estante2Ubs.length,
		fila_order: 'alpha',
		columna_order: 'numeric',
		fila_format: 'alpha',
		columna_format: 'numeric',
		ubicaciones: estante2Ubs
	},
	{
		id: 3,
		nombre: 'Suelto',
		orden_visual: 3,
		filas: 2,
		columnas: 3,
		deposito_id: 1,
		deposito_nombre: 'Depósito Central',
		deleted_at: null,
		created_at: '2024-01-01T00:00:00Z',
		ubicaciones_count: estante3Ubs.length,
		fila_order: 'numeric',
		columna_order: 'numeric',
		fila_format: 'numeric',
		columna_format: 'numeric',
		ubicaciones: estante3Ubs
	},
	{
		id: 4,
		nombre: 'Estante C',
		orden_visual: 1,
		filas: 5,
		columnas: 6,
		deposito_id: 2,
		deposito_nombre: 'Depósito Norte',
		deleted_at: null,
		created_at: '2024-01-01T00:00:00Z',
		ubicaciones_count: estante4Ubs.length,
		fila_order: 'alpha',
		columna_order: 'numeric',
		fila_format: 'alpha',
		columna_format: 'numeric',
		ubicaciones: estante4Ubs
	},
	{
		id: 5,
		nombre: 'Estante D',
		orden_visual: 2,
		filas: 3,
		columnas: 3,
		deposito_id: 2,
		deposito_nombre: 'Depósito Norte',
		deleted_at: null,
		created_at: '2024-01-01T00:00:00Z',
		ubicaciones_count: estante5Ubs.length,
		fila_order: 'alpha',
		columna_order: 'numeric',
		fila_format: 'alpha',
		columna_format: 'numeric',
		ubicaciones: estante5Ubs
	}
];
