# typed: false
# frozen_string_literal: true

class Simplicio < Formula
  desc "AI coding agent that saves up to 96% on tokens"
  homepage "https://simpleti.com.br/simplicio/#start"
  version "1.0.0"
  license "Proprietary"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/wesleysimplicio/simplicio/releases/download/v/simplicio-macos-arm64"
      sha256 "dc45def336dd882961ea72155e8523099cd741e882631a79454ec159bb64299c"
    else
      url "https://github.com/wesleysimplicio/simplicio/releases/download/v/simplicio-macos-arm64"
      sha256 "dc45def336dd882961ea72155e8523099cd741e882631a79454ec159bb64299c"
    end
  end

  def install
    bin.install "simplicio-macos-arm64" => "simplicio"
  end

  test do
    assert_match "simplicio", shell_output("#{bin}/simplicio --version 2>&1", 0)
  end
end
