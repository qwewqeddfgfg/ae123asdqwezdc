/*
 * Copyright (C) 2026 Ardysa
 */
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using ArdysaModsTools.Core.Helpers;
using ArdysaModsTools.Core.Models;
using ArdysaModsTools.Core.Services;
using ArdysaModsTools.Models;
using NUnit.Framework;

namespace ArdysaModsTools.Tests.Services
{
    [TestFixture]
    public class HeroModelIntegrityTests
    {
        private static bool CheckBracketsAndQuotes(string text, out string error)
        {
            int braces = 0;
            bool inQuote = false;
            bool escape = false;

            for (int i = 0; i < text.Length; i++)
            {
                char c = text[i];
                if (escape)
                {
                    escape = false;
                    continue;
                }
                if (c == '\\')
                {
                    escape = true;
                    continue;
                }
                if (c == '"')
                {
                    inQuote = !inQuote;
                    continue;
                }
                if (inQuote) continue;

                if (c == '{') braces++;
                else if (c == '}')
                {
                    braces--;
                    if (braces < 0)
                    {
                        error = $"Unmatched closing brace at char {i}";
                        return false;
                    }
                }
            }

            if (inQuote)
            {
                error = "Unclosed quote string detected";
                return false;
            }
            if (braces != 0)
            {
                error = $"Unbalanced braces: {braces} remaining";
                return false;
            }

            error = string.Empty;
            return true;
        }

        [Test]
        public void Terrorblade_ArcanaAndPrismatic_RetainsAllSlotModelsAndBalancedBrackets()
        {
            // Terrorblade default items:
            // 478: head (horns)
            // 306: back (wings)
            // 307: weapon (blades)
            // 476: armor
            // 913: hero_base
            string vanillaTb =
                "\t\t\"478\"\n\t\t{\n\t\t\t\"name\"\t\t\"TB Head\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"head\"\n\t\t\t\"model_player\"\t\t\"models/heroes/terrorblade/horns.vmdl\"\n\t\t}\n" +
                "\t\t\"306\"\n\t\t{\n\t\t\t\"name\"\t\t\"TB Wings\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"back\"\n\t\t\t\"model_player\"\t\t\"models/heroes/terrorblade/wings.vmdl\"\n\t\t}\n" +
                "\t\t\"307\"\n\t\t{\n\t\t\t\"name\"\t\t\"TB Weapon\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"weapon\"\n\t\t\t\"model_player\"\t\t\"models/heroes/terrorblade/weapon.vmdl\"\n\t\t}\n" +
                "\t\t\"476\"\n\t\t{\n\t\t\t\"name\"\t\t\"TB Armor\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"armor\"\n\t\t\t\"model_player\"\t\t\"models/heroes/terrorblade/armor.vmdl\"\n\t\t}\n" +
                "\t\t\"913\"\n\t\t{\n\t\t\t\"name\"\t\t\"TB Base\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"hero_base\"\n\t\t}\n";

            // Arcana replacement block (5957 / 37161 horns)
            string arcanaHorns =
                "\t\t\"478\"\n\t\t{\n\t\t\t\"name\"\t\t\"Fractal Horns of Inner Abysm\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"head\"\n\t\t\t\"item_rarity\"\t\t\"arcana\"\n\t\t\t\"model_player\"\t\t\"models/heroes/terrorblade/horns_arcana.vmdl\"\n\t\t\t\"visuals\"\n\t\t\t{\n\t\t\t\t\"asset_modifier0\"\n\t\t\t\t{\n\t\t\t\t\t\"type\"\t\t\"particle_create\"\n\t\t\t\t\t\"modifier\"\t\t\"particles/econ/items/terrorblade/terrorblade_horns_arcana/terrorblade_ambient_eyes_arcana_horns.vpcf\"\n\t\t\t\t}\n\t\t\t}\n\t\t}";

            // Particle injection (Rubiline unusual effect)
            string injectedHorns = HeroParticleInjector.Inject(arcanaHorns, "particles/econ/items/terrorblade/terrorblade_horns_arcana/terrorblade_ambient_body_arcana_horns.vpcf");

            var mergedBlocks = new Dictionary<string, (string block, string heroId)>
            {
                ["478"] = (injectedHorns, "npc_dota_hero_terrorblade"),
                ["306"] = ("\t\t\"306\"\n\t\t{\n\t\t\t\"name\"\t\t\"TB Wings\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"back\"\n\t\t\t\"model_player\"\t\t\"models/heroes/terrorblade/wings.vmdl\"\n\t\t}", "npc_dota_hero_terrorblade"),
                ["307"] = ("\t\t\"307\"\n\t\t{\n\t\t\t\"name\"\t\t\"TB Weapon\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"weapon\"\n\t\t\t\"model_player\"\t\t\"models/heroes/terrorblade/weapon.vmdl\"\n\t\t}", "npc_dota_hero_terrorblade"),
                ["476"] = ("\t\t\"476\"\n\t\t{\n\t\t\t\"name\"\t\t\"TB Armor\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"armor\"\n\t\t\t\"model_player\"\t\t\"models/heroes/terrorblade/armor.vmdl\"\n\t\t}", "npc_dota_hero_terrorblade"),
            };

            // Overlay onto vanilla
            string resultText = vanillaTb;
            foreach (var kv in mergedBlocks)
            {
                var existing = KeyValuesBlockHelper.ExtractBlockById(resultText, kv.Key);
                Assert.That(existing, Is.Not.Null, $"Slot {kv.Key} must exist in vanilla text");
                var overlaid = KeyValuesBlockHelper.OverlayBlockPreservingStructure(existing, kv.Value.block);
                resultText = KeyValuesBlockHelper.ReplaceIdBlock(resultText, kv.Key, overlaid, out bool ok);
                Assert.That(ok, Is.True, $"Replacing block {kv.Key} must succeed");
            }

            // Verify KeyValues balance
            Assert.That(CheckBracketsAndQuotes(resultText, out var err), Is.True, $"Balance error: {err}");

            // Verify every required slot retains valid model_player
            string[] checkSlots = { "478", "306", "307", "476" };
            foreach (var id in checkSlots)
            {
                var block = KeyValuesBlockHelper.ExtractBlockById(resultText, id);
                Assert.That(block, Is.Not.Null, $"Block {id} must exist in output");
                bool hasModel = KeyValuesBlockHelper.TryGetTopLevelValue(block, "model_player", out var mp) && !string.IsNullOrWhiteSpace(mp);
                Assert.That(hasModel, Is.True, $"Slot item {id} must retain a valid model_player, was: {block}");
            }
        }

        [Test]
        public void Pudge_Persona_RetainsAllPersonaSlotModelsAndBalancedBrackets()
        {
            // Pudge Persona slots:
            // 696: weapon_persona_1
            // 697: offhand_weapon_persona_1
            // 712: armor_persona_1
            // 713: head_persona_1
            // 805: arms_persona_1
            // 709: persona_selector
            string vanillaPudge =
                "\t\t\"696\"\n\t\t{\n\t\t\t\"name\"\t\t\"Pudge Hook\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"weapon_persona_1\"\n\t\t\t\"model_player\"\t\t\"models/heroes/pudge_cute/pudge_cute_hook.vmdl\"\n\t\t}\n" +
                "\t\t\"697\"\n\t\t{\n\t\t\t\"name\"\t\t\"Pudge Offhand\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"offhand_weapon_persona_1\"\n\t\t\t\"model_player\"\t\t\"models/heroes/pudge_cute/pudge_cute_offhand.vmdl\"\n\t\t}\n" +
                "\t\t\"712\"\n\t\t{\n\t\t\t\"name\"\t\t\"Pudge Armor\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"armor_persona_1\"\n\t\t\t\"model_player\"\t\t\"models/heroes/pudge_cute/pudge_cute_costume.vmdl\"\n\t\t}\n" +
                "\t\t\"713\"\n\t\t{\n\t\t\t\"name\"\t\t\"Pudge Head\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"head_persona_1\"\n\t\t\t\"model_player\"\t\t\"models/heroes/pudge_cute/pudge_cute_hair.vmdl\"\n\t\t}\n" +
                "\t\t\"805\"\n\t\t{\n\t\t\t\"name\"\t\t\"Pudge Arms\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"arms_persona_1\"\n\t\t\t\"model_player\"\t\t\"models/heroes/pudge_cute/pudge_cute_arms.vmdl\"\n\t\t}\n" +
                "\t\t\"709\"\n\t\t{\n\t\t\t\"name\"\t\t\"Pudge Persona\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"persona_selector\"\n\t\t}\n";

            // Modded custom Doll of the Dead Hook
            string dollHook =
                "\t\t\"696\"\n\t\t{\n\t\t\t\"name\"\t\t\"Doll of the Dead Hook\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"weapon_persona_1\"\n\t\t\t\"item_rarity\"\t\t\"legendary\"\n\t\t\t\"model_player\"\t\t\"models/items/pudge_cute/pudge_cute_calavera/pudge_cute_calavera_weapon.vmdl\"\n\t\t}";

            // Modded custom Doll of the Dead Arms
            string dollArms =
                "\t\t\"805\"\n\t\t{\n\t\t\t\"name\"\t\t\"Doll of the Dead Arms\"\n\t\t\t\"prefab\"\t\t\"default_item\"\n\t\t\t\"item_slot\"\t\t\"arms_persona_1\"\n\t\t\t\"item_rarity\"\t\t\"legendary\"\n\t\t\t\"model_player\"\t\t\"models/items/pudge_cute/pudge_cute_calavera/pudge_cute_calavera_arms.vmdl\"\n\t\t}";

            var mergedBlocks = new Dictionary<string, (string block, string heroId)>
            {
                ["696"] = (dollHook, "npc_dota_hero_pudge"),
                ["805"] = (dollArms, "npc_dota_hero_pudge"),
            };

            string resultText = vanillaPudge;
            foreach (var kv in mergedBlocks)
            {
                var existing = KeyValuesBlockHelper.ExtractBlockById(resultText, kv.Key);
                Assert.That(existing, Is.Not.Null, $"Slot {kv.Key} must exist in vanilla text");
                var overlaid = KeyValuesBlockHelper.OverlayBlockPreservingStructure(existing, kv.Value.block);
                resultText = KeyValuesBlockHelper.ReplaceIdBlock(resultText, kv.Key, overlaid, out bool ok);
                Assert.That(ok, Is.True, $"Replacing block {kv.Key} must succeed");
            }

            // Verify KeyValues balance
            Assert.That(CheckBracketsAndQuotes(resultText, out var err), Is.True, $"Balance error: {err}");

            // Verify all persona slots retain valid model_player
            string[] checkSlots = { "696", "697", "712", "713", "805" };
            foreach (var id in checkSlots)
            {
                var block = KeyValuesBlockHelper.ExtractBlockById(resultText, id);
                Assert.That(block, Is.Not.Null, $"Block {id} must exist in output");
                bool hasModel = KeyValuesBlockHelper.TryGetTopLevelValue(block, "model_player", out var mp) && !string.IsNullOrWhiteSpace(mp);
                Assert.That(hasModel, Is.True, $"Persona slot {id} must retain a valid model_player, was: {block}");
            }
        }
    }
}
