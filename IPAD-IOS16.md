# mlx-swift — branche `ipad-ios16`

> Vibecodé par Claude pour iPad Pro 12,9" M1 (iOS 16.6.1, TrollStore). Basé sur mlx-swift **0.32.3** officiel.

But : faire tourner MLX récent (et donc les modèles récents de mlx-swift-lm) sur **iOS 16**.

## Changements (« polyfills »)

| Fichier | Pourquoi | Quoi |
|---|---|---|
| `Package.swift` | MLX déclare iOS 17 | `.iOS(.v16)` ; dossier `Source/Cmlx/ios16-overrides` cherché en premier (C et C++) |
| `Source/Cmlx/ios16-overrides/mlx/c/private/io.h` | `std::format` (mlx-c) exige des fonctions libc++ d'iOS 16.3+ | copie sans `std::format` (concaténation). **Ne jamais** utiliser `_LIBCPP_DISABLE_AVAILABILITY` : l'app plantait au lancement sur iOS 16.6 (`exception_ptr::__from_native_exception_pointer` absent du libc++ système) |
| `Source/Cmlx/mlx-generated/metal/bf16.h` | le type Metal `bfloat` natif exige Metal 3.1 = iOS 17 | `bfloat` **logiciel** (`_MLX_BFloat16`, repris de mlx-swift 0.29.1) |
| `…/metal/utils.h`, `…/metal/fp8.h` | `as_type` sur le bfloat natif | lecture / écriture des bits (`bits_`, `bits_to_bfloat`) |
| `…/metal/complex.h` | complexe bfloat = vecteur Metal de bfloat (impossible en logiciel) | complexe bfloat retiré (non utilisé par les modèles) |
| `…/metal/dot.h` | lecture `vec<T,4>` de bfloat | lecture élément par élément pour le bfloat |

| `Source/Cmlx/ios16-overrides/src/metal_device.cpp` (original `mlx/backend/metal/device.cpp` exclu) | MLX compile ses noyaux à la volée en Metal ≥ 3.1 (iOS 17) | branche **Metal 3.0** pour iOS 16 ; `MLX_METAL_LANGUAGE_VERSION=30` force Metal 3.0 sur Mac pour tester |

Seuls les fichiers de `mlx-generated/metal` sont compilés (le dossier `kernels` du sous-module `mlx` est exclu) :
le sous-module n'est pas modifié.

À savoir : le bfloat logiciel est plus lent que le natif ; préférer des modèles en float16 ou quantifiés.
Les noyaux compilés **à la volée** (JIT) utilisent des copies embarquées de ces en-têtes dans
`Source/Cmlx/mlx-generated/*.cpp` : elles reçoivent les mêmes corrections.

**Pour remonter sur une nouvelle version de MLX** : `tools/update-mlx.sh`, puis `python3 tools/ipad-ios16-patch.py`
(applique tout, échoue s'il reste du `bfloat` natif), puis tester sur Mac avec `MLX_METAL_LANGUAGE_VERSION=30`
(mêmes conditions de compilation que l'iPad sous iOS 16).
