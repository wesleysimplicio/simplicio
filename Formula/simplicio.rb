# typed: false
# frozen_string_literal: true

class Simplicio < Formula
  desc "AI coding agent that saves up to 96% on tokens"
  homepage "https://simpleti.com.br/simplicio/#start"
  version "3.5.2"
  license "Proprietary"
  url "https://github.com/wesleysimplicio/simplicio/releases/download/v3.5.2/simplicio-macos-arm64"
  sha256 "931bc6d8f45c1b1e586070f8f5ac4a762861bc9157c70f75aaa4ebfad8ff27bb"
  depends_on :macos
  depends_on arch: :arm64

  def install
    bin.install "simplicio-macos-arm64" => "simplicio"
  end

  test do
    assert_match "simplicio", shell_output("#{bin}/simplicio --version 2>&1", 0)
  end
end
