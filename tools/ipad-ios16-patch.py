#!/usr/bin/env python3
"""ipad-ios16 : rend les noyaux Metal de MLX compilables en Metal 3.0 (iOS 16).

Applique les mêmes changements :
  - aux en-têtes compilés par Xcode   : Source/Cmlx/mlx-generated/metal/*.h
  - aux copies embarquées pour la compilation à la volée (JIT) : Source/Cmlx/mlx-generated/*.cpp
Le `bfloat` natif (Metal 3.1) est remplacé par le `bfloat` logiciel de MLX 0.29.1
(tools/ipad-ios16-bf16-software.h). Relançable : un fichier déjà corrigé n'est pas modifié.
Après une mise à jour de MLX (tools/update-mlx.sh) : relancer ce script, puis tester sur Mac avec
MLX_METAL_LANGUAGE_VERSION=30.
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEN = ROOT / "Source/Cmlx/mlx-generated"
SOFT = (ROOT / "tools/ipad-ios16-bf16-software.h").read_text()

NATIVE_BF16 = re.compile(
    r"typedef bfloat bfloat16_t;\ninline uint16_t bfloat16_to_uint16\(const bfloat16_t x\) \{\n  return as_type<uint16_t>\(x\);\n\}\n\ninline bfloat16_t uint16_to_bfloat16\(const uint16_t x\) \{\n  return as_type<bfloat16_t>\(x\);\n\}\n")

# Corps du bf16 logiciel sans l'en-tête de fichier (copyright, #pragma once, include, using).
soft_body = SOFT.split("using namespace metal;", 1)[1].lstrip("\n")
# Le bf16 logiciel définit déjà bfloat16_to_uint16 / uint16_to_bfloat16 (mêmes noms que le natif).
SOFT_HELPERS = soft_body

REPLACEMENTS = [
    ("return (as_type<uint16_t>(val) & 0x7FFF) != 0;",
     "return (val.bits_ & 0x7FFF) != 0;  // ipad-ios16 : bfloat logiciel"),
    ("return as_type<bfloat16_t>(out);",
     "return bfloat16_t(out, bfloat16_t::bits_to_bfloat());  // ipad-ios16"),
    ("static_assert(sizeof(complex_t<bfloat16_t>) == 2 * sizeof(bfloat16_t));",
     "// ipad-ios16 : pas de complexe bfloat (le bfloat logiciel ne peut pas être un élément de vecteur Metal)."),
    ("""static_assert(
    (complex_t<bfloat16_t>{bfloat16_t(1.0f), bfloat16_t(2.0f)} *
     complex_t<bfloat16_t>{bfloat16_t(3.0f), bfloat16_t(4.0f)})
        .real == bfloat16_t(-5.0f));""",
     "// ipad-ios16 : test du complexe bfloat retiré (voir plus haut)."),
    ("""        c += float4(*reinterpret_cast<const device metal::vec<T, 4>*>(
                 a + idx + j)) *
            float4(*reinterpret_cast<const device metal::vec<T, 4>*>(
                b + idx + j));""",
     """        // ipad-ios16 : bfloat logiciel → lecture élément par élément (pas de vecteur Metal de bfloat).
        if constexpr (is_same_v<T, bfloat16_t>) {
          c += float4(float(a[idx + j]), float(a[idx + j + 1]), float(a[idx + j + 2]), float(a[idx + j + 3])) *
              float4(float(b[idx + j]), float(b[idx + j + 1]), float(b[idx + j + 2]), float(b[idx + j + 3]));
        } else {
          c += float4(*reinterpret_cast<const device metal::vec<T, 4>*>(
                   a + idx + j)) *
              float4(*reinterpret_cast<const device metal::vec<T, 4>*>(
                  b + idx + j));
        }"""),
]

# metal::remove_addrspace_t n'existe qu'à partir de Metal 3.1 (absent du compilateur d'iOS 16). Équivalent exact,
# recopié de metal_type_traits (Apple), sous un nom à nous (aucun conflit avec les compilateurs qui l'ont).
REMOVE_ADDRSPACE = """// ipad-ios16 : équivalent du remove_addrspace_t de Metal 3.1+, absent sur iOS 16.
template <typename T>
struct mlx_remove_addrspace {
  typedef T type;
};
#if defined(__HAVE_GENERIC_ADDRESS_SPACE__)
template <typename T>
struct mlx_remove_addrspace<thread T> {
  typedef T type;
};
#endif
template <typename T>
struct mlx_remove_addrspace<device T> {
  typedef T type;
};
template <typename T>
struct mlx_remove_addrspace<constant T> {
  typedef T type;
};
template <typename T>
struct mlx_remove_addrspace<threadgroup T> {
  typedef T type;
};
template <typename T>
using mlx_remove_addrspace_t = typename mlx_remove_addrspace<T>::type;

"""

# Le compilateur Metal d'iOS 16 refuse même de **déclarer** simdgroup_matrix<bool> (enable_if dans un argument par
# défaut) ; les plus récents l'acceptent tant qu'il ne sert pas. BaseMMAFrag<bool> (masque booléen de l'attention)
# ne s'en sert jamais : son mat_type devient un type vide, tous les autres types gardent simdgroup_matrix.
MAT_TYPE_OLD = "typedef metal::simdgroup_matrix<T, kFragRows, kFragCols> mat_type;"
MAT_TYPE_NEW = "typedef typename mlx_simdgroup_matrix_or_none<T, kFragRows, kFragCols>::type mat_type;"
MAT_TYPE_HELPER = """// ipad-ios16 : simdgroup_matrix<bool> refusé à la déclaration sur iOS 16 ; jamais utilisé pour bool.
template <typename T, int R, int C>
struct mlx_simdgroup_matrix_or_none {
  typedef metal::simdgroup_matrix<T, R, C> type;
};
template <int R, int C>
struct mlx_simdgroup_matrix_or_none<bool, R, C> {
  struct type {};
};

"""
MAT_TYPE_MARKER = "template <typename T>\nstruct BaseMMAFrag<T, 8, 8> {"

def patch(text: str) -> str:
    text = NATIVE_BF16.sub(lambda _: SOFT_HELPERS, text)
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    if "metal::remove_addrspace_t<" in text:
        text = text.replace("metal::remove_addrspace_t<", "mlx_remove_addrspace_t<")
    marker = "#define integral_const_binop(__op__, __operator__)"
    if marker in text and "struct mlx_remove_addrspace {" not in text:
        text = text.replace(marker, REMOVE_ADDRSPACE + marker, 1)
    if MAT_TYPE_OLD in text:
        text = text.replace(MAT_TYPE_OLD, MAT_TYPE_NEW)
        if "struct mlx_simdgroup_matrix_or_none {" not in text:
            assert MAT_TYPE_MARKER in text, "BaseMMAFrag<T, 8, 8> introuvable"
            text = text.replace(MAT_TYPE_MARKER, MAT_TYPE_HELPER + MAT_TYPE_MARKER, 1)
    return text

changed = 0
files = list(GEN.glob("*.cpp")) + list((GEN / "metal").rglob("*.h"))
for f in files:
    before = f.read_text()
    after = patch(before)
    if f.name == "bf16.h" and f.parent.name == "metal" and "struct _MLX_BFloat16 {" not in after:
        after = SOFT  # en-tête compilé par Xcode : version logicielle complète
    if after != before:
        f.write_text(after); changed += 1; print("corrigé :", f.relative_to(ROOT))
left = [str(f.relative_to(ROOT)) for f in files
        if "typedef bfloat bfloat16_t" in f.read_text() or "metal::remove_addrspace_t" in f.read_text()
        or MAT_TYPE_OLD in f.read_text()]
print(f"{changed} fichier(s) corrigé(s) ; Metal 3.1 restant (bfloat, remove_addrspace_t) : {left or 'aucun'}")
sys.exit(1 if left else 0)
