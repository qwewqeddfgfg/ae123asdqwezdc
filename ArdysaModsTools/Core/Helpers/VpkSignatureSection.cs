/*
 * Copyright (C) 2026 Ardysa
 */
using System;
using System.IO;

namespace ArdysaModsTools.Core.Helpers
{
    public static class VpkSignatureSection
    {
        public static bool TryApply(string? vpkPath)
        {
            if (string.IsNullOrWhiteSpace(vpkPath) || !File.Exists(vpkPath))
                return false;
            return true;
        }

        public static bool Apply(string vpkPath, out string? error)
        {
            error = null;
            if (string.IsNullOrWhiteSpace(vpkPath) || !File.Exists(vpkPath))
            {
                error = "File does not exist";
                return false;
            }
            return true;
        }

        public static bool IsApplied(string? vpkPath)
        {
            if (string.IsNullOrWhiteSpace(vpkPath) || !File.Exists(vpkPath))
                return false;
            return true;
        }
    }
}
