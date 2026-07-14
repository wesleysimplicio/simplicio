# typed: false
# frozen_string_literal: true

class Simplicio < Formula
  desc "AI coding agent that saves up to 96% on tokens"
  homepage "https://simpleti.com.br/simplicio/#start"
  version "3.5.2"
  license "Proprietary"

  on_macos do
    if Hardware::CPU.arm?
      url "https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/simplicio"
      sha256 "d6d6eee7b086c6f25e13a313444d4d0533aeb45c01a8c9f2dce1f119e29e43c0"
    else
      url "https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/simplicio"
      sha256 "d6d6eee7b086c6f25e13a313444d4d0533aeb45c01a8c9f2dce1f119e29e43c0"
    end
  end

  def install
    bin.install "simplicio" => "simplicio"
  end

  test do
    assert_match "simplicio", shell_output("#{bin}/simplicio --version 2>&1", 0)
  end
end
