# mlx-swift — branche `ipad-ios16`

> Vibecodé par Claude pour iPad Pro 12,9" M1 (iOS 16.6.1, TrollStore). Basé sur mlx-swift **0.32.3** officiel.

But : faire tourner MLX récent (et donc les modèles récents de mlx-swift-lm) sur **iOS 16**.

## Changements (« polyfills »)

| Fichier | Pourquoi | Quoi |
|---|---|---|
| `Package.swift` | MLX déclare iOS 17 | `.iOS(.v16)` ; `_LIBCPP_DISABLE_AVAILABILITY` (`std::format` de flottants marqué iOS 16.3+, présent à l'exécution dès 16.3) |
| `Source/Cmlx/mlx-generated/metal/bf16.h` | le type Metal `bfloat` natif exige Metal 3.1 = iOS 17 | `bfloat` **logiciel** (`_MLX_BFloat16`, repris de mlx-swift 0.29.1) |
| `…/metal/utils.h`, `…/metal/fp8.h` | `as_type` sur le bfloat natif | lecture / écriture des bits (`bits_`, `bits_to_bfloat`) |
| `…/metal/complex.h` | complexe bfloat = vecteur Metal de bfloat (impossible en logiciel) | complexe bfloat retiré (non utilisé par les modèles) |
| `…/metal/dot.h` | lecture `vec<T,4>` de bfloat | lecture élément par élément pour le bfloat |

Seuls les fichiers de `mlx-generated/metal` sont compilés (le dossier `kernels` du sous-module `mlx` est exclu) :
le sous-module n'est pas modifié.

À savoir : le bfloat logiciel est plus lent que le natif ; préférer des modèles en float16 ou quantifiés.
Pour remonter sur une nouvelle version : refaire ces mêmes changements (garder ce tableau à jour).
