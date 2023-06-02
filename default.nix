{ lib, python3Packages, poetry2nix, wrapGAppsHook, gobject-introspection, restic }:
python3Packages.buildPythonApplication {
  name = "igotchuu";
  version = "0.1.0";

  src = poetry2nix.cleanPythonSources {
    src = ./.;
  };

  buildInputs = [ gobject-introspection ];
  nativeBuildInputs = [ wrapGAppsHook ];
  propagatedBuildInputs = with python3Packages; [
    pygobject3 btrfsutil python-unshare
  ];

  # There are no tests for now
  doCheck = false;
  # No double-wrapping
  dontWrapGApps = true;

  postInstall = ''
    install -Dm644 ./dbus-policy.conf $out/share/dbus-1/system.d/com.nyantec.IGotChuu.conf
  '';

  preFixup = ''
    makeWrapperArgs+=(
      --prefix PATH ":" "${lib.makeBinPath [ restic ]}"
      "''${gappsWrapperArgs[@]}"
      )
    '';

  meta = with lib; {
    mainProgram = "igotchuu";
    homepage = "https://github.com/nyantec/igotchuu";
    description = "Backup script wrapping Restic with btrfs snapshots and other goodies";
    maintainers = with maintainers; [
      vikanezrimaya
    ];
    license = licenses.miros;
    platforms = platforms.linux;
  };
}
