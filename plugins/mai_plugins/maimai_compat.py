from maimai_py.enums import Version, current_version, divingfish_to_version


def patch_maimai_py_versions() -> None:
    prism_plus = Version.MAIMAI_DX_PRISM_PLUS
    divingfish_to_version.setdefault("maimai でらっくす PRiSM PLUS", prism_plus)
    divingfish_to_version.setdefault("maimai でらっくす PRISM PLUS", prism_plus)

    if current_version.value < prism_plus.value:
        import maimai_py.enums as enums
        import maimai_py.maimai as maimai_module

        enums.current_version = prism_plus
        maimai_module.current_version = prism_plus
