{ lib, nix-gitignore, python3Packages, wrapGAppsHook, gobject-introspection, restic }:
let
  cleanSources = { src }:
  let
    nixFilter = name: type: ! (
      (type == "regular" && lib.strings.hasSuffix ".nix" name)
    );
  in lib.cleanSourceWith {
    filter = lib.cleanSourceFilter;
    src = lib.cleanSourceWith {
      filter = nix-gitignore.gitignoreFilterPure nixFilter [ ./.gitignore ] src;
      inherit src;
    };
  };
in
python3Packages.buildPythonApplication {
  name = "igotchuu";
  version = "0.1.0";

  src = cleanSources {
    src = ./.;
  };

  buildInputs = [ gobject-introspection ];
  nativeBuildInputs = [ wrapGAppsHook ];
  propagatedBuildInputs = with python3Packages; [
    pygobject3 btrfsutil python-unshare click
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
