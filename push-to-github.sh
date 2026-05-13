#!/bin/bash

# Script para pushear el proyecto a GitHub

echo "🚀 Preparando para pushear a GitHub..."

# Inicializar git si no existe
if [ ! -d ".git" ]; then
    git init
    echo "✅ Repo Git inicializado"
fi

# Agregar archivos
git add .
echo "✅ Archivos agregados"

# Commit inicial
git commit -m "Initial commit: WhatsApp Facturas API with FastAPI, Claude Vision, and Firestore"
echo "✅ Commit realizado"

echo ""
echo "📝 Próximos pasos:"
echo ""
echo "1. Crear un nuevo repo en GitHub vacío (sin README)"
echo "2. Copiar la URL del repo (ej: https://github.com/tu-usuario/nombre-repo.git)"
echo "3. Ejecutar:"
echo "   git remote add origin https://github.com/tu-usuario/nombre-repo.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "4. En Vercel:"
echo "   - Conectar el repo GitHub"
echo "   - Agregar variables de entorno"
echo "   - Deploy automático"
