# typed: false
# frozen_string_literal: true

class Simplicio < Formula
  desc "AI coding agent that saves up to 96% on tokens"
  homepage "https://simpleti.com.br/simplicio/#start"
  version "1.0.4"
  license "Proprietary"

  on_macos do
    if Hardware::CPU.arm?
      url "https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/simplicio"
      sha256 "36dd2cbb21ecd7ac2bdd944dd0f90b051b8db6d6d6b4eb736a2906f533f74b55"
    else
      url "https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/simplicio"
      sha256 "36dd2cbb21ecd7ac2bdd944dd0f90b051b8db6d6d6b4eb736a2906f533f74b55"
    end
  end

  def install
    bin.install "simplicio" => "simplicio"
  end

  test do
    assert_match "simplicio", shell_output("#{bin}/simplicio --version 2>&1", 0)
  end
end
