#!/usr/bin/env python3
"""Generate a Homebrew tap formula file from a GitHub release tag."""

import argparse
import sys
import urllib.request


ASSETS = {
    "darwin-arm64": {"os": "macos", "cpu": "arm"},
    "darwin-amd64": {"os": "macos", "cpu": "intel"},
    "linux-amd64": {"os": "linux", "cpu": "intel"},
    "linux-arm64": {"os": "linux", "cpu": "arm"},
}

TEMPLATE = """\
class {class_name} < Formula
  desc "{desc}"
  homepage "{homepage}"
  version "{version}"

  on_macos do
    if Hardware::CPU.intel?
      url "{base_url}/geenii-darwin-amd64.tar.gz"
      sha256 "{sha_darwin_amd64}"

      def install
        libexec.install Dir["*"]
        bin.install_symlink libexec/"geenii"/"geenii"
      end
    end
    if Hardware::CPU.arm?
      url "{base_url}/geenii-darwin-arm64.tar.gz"
      sha256 "{sha_darwin_arm64}"

      def install
        libexec.install Dir["*"]
        bin.install_symlink libexec/"geenii"/"geenii"
      end
    end
  end

  on_linux do
    if Hardware::CPU.intel?
      if Hardware::CPU.is_64_bit?
        url "{base_url}/geenii-linux-amd64.tar.gz"
        sha256 "{sha_linux_amd64}"

        def install
          libexec.install Dir["*"]
          bin.install_symlink libexec/"geenii"/"geenii"
        end
      end
    end
    if Hardware::CPU.arm?
      if Hardware::CPU.is_64_bit?
        url "{base_url}/geenii-linux-arm64.tar.gz"
        sha256 "{sha_linux_arm64}"

        def install
          libexec.install Dir["*"]
          bin.install_symlink libexec/"geenii"/"geenii"
        end
      end
    end
  end
end
"""


def fetch_sha256(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode().strip().split()[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="Release tag name (e.g. v0.1.0)")
    parser.add_argument("--repo", default="fm-labs/geenii", help="GitHub owner/repo")
    parser.add_argument("--class-name", default="Geenii", help="Formula class name")
    parser.add_argument("--desc", default="geenii", help="Formula description")
    parser.add_argument("--homepage", default=None, help="Homepage URL (defaults to repo URL)")
    parser.add_argument("-o", "--output", default=None, help="Output file (default: stdout)")
    args = parser.parse_args()

    homepage = args.homepage or f"https://github.com/{args.repo}"
    version = args.tag.lstrip("v")
    base_url = f"https://github.com/{args.repo}/releases/download/{args.tag}"

    shas = {}
    for variant in ["darwin-amd64", "darwin-arm64", "linux-amd64", "linux-arm64"]:
        sha_url = f"{base_url}/geenii-{variant}.tar.gz.sha256"
        print(f"Fetching {sha_url} ...", file=sys.stderr)
        shas[variant] = fetch_sha256(sha_url)

    formula = TEMPLATE.format(
        class_name=args.class_name,
        desc=args.desc,
        homepage=homepage,
        version=version,
        base_url=base_url,
        sha_darwin_amd64=shas["darwin-amd64"],
        sha_darwin_arm64=shas["darwin-arm64"],
        sha_linux_amd64=shas["linux-amd64"],
        sha_linux_arm64=shas["linux-arm64"],
    )

    if args.output:
        with open(args.output, "w") as f:
            f.write(formula)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(formula)


if __name__ == "__main__":
    main()
