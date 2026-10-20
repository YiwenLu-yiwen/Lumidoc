import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Check, ChevronDown, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/context/LanguageContext";
import { useTheme } from "@/context/ThemeContext";
import { supportedLanguages } from "@/utils/language";

/** Shared navigation control for the public homepage and project workspace. */
export function LanguageSwitcher() {
  const { currentLanguage, setLanguage, t } = useLanguage();
  const { isDarkMode } = useTheme();
  const selected = supportedLanguages.find(
    (language) => language.code === currentLanguage,
  );
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <Button
          variant="ghost"
          size="sm"
          aria-label={t("language")}
          title={t("language")}
          className={`h-9 gap-2 rounded-md px-2.5 ${isDarkMode ? "text-gray-300 hover:bg-gray-800 hover:text-white" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"}`}
        >
          <Globe className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">{selected?.name}</span>
          <ChevronDown
            className="hidden h-3 w-3 opacity-60 sm:block"
            aria-hidden="true"
          />
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          collisionPadding={12}
          className={`z-[100] min-w-40 rounded-lg border p-1 shadow-lg ${isDarkMode ? "border-gray-700 bg-[#2a2a2a] text-gray-200" : "border-gray-200 bg-white text-gray-700"}`}
        >
          <DropdownMenu.RadioGroup
            value={currentLanguage}
            onValueChange={setLanguage}
          >
            {supportedLanguages.map((language) => (
              <DropdownMenu.RadioItem
                key={language.code}
                value={language.code}
                className={`flex cursor-pointer items-center justify-between gap-6 rounded-md px-3 py-2 text-sm outline-none ${isDarkMode ? "data-[highlighted]:bg-gray-700" : "data-[highlighted]:bg-gray-100"}`}
              >
                <span lang={language.code}>{language.name}</span>
                <DropdownMenu.ItemIndicator>
                  <Check className="h-4 w-4" aria-hidden="true" />
                </DropdownMenu.ItemIndicator>
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
